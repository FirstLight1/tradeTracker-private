import json
from typing import Any
from io import BytesIO
import sqlite3

from tradeTracker.services.models import SaleCorrectionItem, SaleCorrectionRequest
from tradeTracker.generateInvoice import generateCreditNote

class SaleCorrectionService:
    def __init__(self, db):
        self.db = db

    def _return_shipping(self, sale_id:int, shipping_value: float = 0) -> float:
        try:
            self.db.execute(
                "UPDATE sales SET shipping_info = shipping_info - ? WHERE id = ?",
                (shipping_value, sale_id),
            )
            return shipping_value
        except Exception:
            raise sqlite3.Error("Failed to update shipping")


    def _order_return(self,sale_id:int, cards: list[SaleCorrectionItem] | None, sealed:list[SaleCorrectionItem] | None)-> float:

        #TODO: when cards and sealed DTO exist
        returned_value = 0.0
        if cards:
            returned_value += self._return_cards(cards)

        if sealed:
            returned_value += self._return_sealed(sealed)


        self._return_bulk(sale_id)
        return returned_value

    def _return_cards(self, cards: list[SaleCorrectionItem] | None, sale_id: int) -> float:
        if not cards:
            return 0.0
        cardPlaceholder = ",".join("?" for _ in cards)
        card_ids = [card.id for card in cards]
    
        cards_sum= self.db.execute(
            f"SELECT COALESCE(SUM(sell_price), 0) FROM sale_items WHERE card_id IN ({cardPlaceholder})",
            card_ids,
        ).fetchone()[0]

        try:
            self.db.execute(
                f"UPDATE cards SET sold_date = NULL WHERE sale_id = ? AND id IN ({cardPlaceholder})", (sale_id,card_ids)
            )
            self.db.execute(f"DELETE FROM sale_items WHERE card_id IN ({cardPlaceholder})", card_ids)
        except Exception:
            raise sqlite3.Error("Failed to update database")
        return cards_sum or 0.0

    def _return_sealed(self, sealed: list[SaleCorrectionItem] | None, sale_id: int) -> float:
        if not sealed:
            return 0.0

        sealedPlan = []
        for entry in sealed:
            sealed_id = entry.id
            returnQuantity = entry.quantity
            if not sealed_id or not returnQuantity or returnQuantity <= 0:
                continue
            row = self.db.execute(
                "SELECT quantity, sell_price FROM sealed WHERE id = ? AND sale_id = ?", (sealed_id,sale_id)
            ).fetchone()
            if row is None:
                raise ValueError(f"Sealed item {sealed_id} not found")
            if returnQuantity > row["quantity"]:
                raise ValueError(f"returnQuantity exceeds available {row['quantity']} for sealed item {sealed_id}")
            sealedPlan.append(
                (sealed_id, returnQuantity, row["quantity"], row["market_value"] or 0)
            )

        returned_sum = 0.0
        for sealed_id, returnQuantity, orig_quantity, mv in sealedPlan:
            returned_sum += mv * returnQuantity
            try:
                if returnQuantity == orig_quantity:
                    self.db.execute("UPDATE sealed SET sale_id = NULL WHERE id = ?", (sealed_id,))
                else:
                    self.db.execute(
                        "UPDATE sealed SET quantity = quantity - ? WHERE id = ?",
                        (returnQuantity, sealed_id),
                    )
                    self.db.execute(
                        """INSERT INTO sealed (name, normalized_name, quantity, language, price, market_value,
                                            date, sale_id, auction_id, opened, cardMarketID)
                        SELECT name, normalized_name, ?, language, price, market_value,
                                date, NULL, auction_id, opened, cardMarketID
                        FROM sealed WHERE id = ?""",
                        (returnQuantity, sealed_id),
                    )
            except Exception:
                raise sqlite3.Error
        return returned_sum

    def _return_bulk(self, sale_id: int):
        
        bulk_sales_rows = self.db.execute(
            "SELECT item_type, quantity FROM bulk_sales WHERE sale_id = ?", (sale_id,)
        ).fetchall()
        for bs_row in bulk_sales_rows:
            target = self.db.execute(
                "SELECT id FROM bulk_items WHERE item_type = ? ORDER BY auction_id DESC LIMIT 1",
                (bs_row["item_type"],),
            ).fetchone()
            if target:
                try:
                    self.db.execute(
                        "UPDATE bulk_items SET quantity = quantity + ? WHERE id = ?",
                        (bs_row["quantity"], target["id"]),
                    )
                except:
                    raise sqlite3.Error("Failed to update bulk items")

    #TODO: change to DTO
    def generate_credit_note(self, sale_id: int, sale_correction_data: SaleCorrectionRequest) -> tuple[dict[str, str | bytes], int]:
        returned_value = 0.0
        try:
            returned_value += self._return_cards(sale_correction_data.cards, sale_id)
            returned_value += self._return_sealed(sale_correction_data.sealed, sale_id)
            self._return_bulk(sale_id)
            returned_value += self._return_shipping(sale_id,sale_correction_data.shipping.shippingPrice)

            #TODO: abstract this
            creditNoteNum = None
            for attempt in range(3):
                row = self.db.execute(
                    "SELECT COALESCE(MAX(record_number), 0) + 1 FROM sales_correction WHERE change_type = 'credit'"
                ).fetchone()
                creditNoteNum: int = row[0]
                try:
                    self.db.execute(
                        "INSERT INTO sales_correction (sale_id, record_number, change_type, value_change) VALUES (?, ?, ?, ?)",
                        (sale_id, creditNoteNum, "credit", returned_value),
                    )
                    break
                except sqlite3.IntegrityError as e:
                    if "UNIQUE constraint" not in str(e):
                        self.db.rollack()
                        raise Exception("IntegrityError on sales_correction")
                    if attempt == 2:
                        self.db.rollback()
                        raise Exception("Exhausted retries") 
                    continue

            try:
                pdf, cn_num = generateCreditNote(
                    sale_correction_data.reciever,
                    sale_correction_data.cards,
                    sale_correction_data.sealed,
                    shipping=sale_correction_data.shipping,
                    original_invoice_num=sale_correction_data.original_invoice_num,
                    cn_num=creditNoteNum,
                )
            except Exception as e:
                self.db.rollback()
                raise Exception("Credit note generation failed %s", e)
        except Exception as e:
            self.db.rollback()
            raise Exception(f"{e}")
        self.db.commit()
        return pdf, cn_num
