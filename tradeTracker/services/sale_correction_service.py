import json
from typing import Any
from io import BytesIO
import sqlite3

from tradeTracker.services.models import SaleCorrectionItem, SaleCorrectionRequest

class SaleCorrectionService:
    def __init__(self, db):
        self.db = db

    def _return_shipping(self, sale_id:int, shipping_value: float = 0):
        try:
            self.db.execute(
                "UPDATE sales SET shipping_info = shipping_info - ? WHERE id = ?",
                (shipping_value, sale_id),
            )
        except Exception:
            self.db.rollback()
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

    def _return_cards(self, cards: list[SaleCorrectionItem]) -> float:
        cardPlaceholder = ",".join("?" for _ in cards)
        card_ids = [card.id for card in cards]
    
        cards_sum= self.db.execute(
            f"SELECT COALESCE(SUM(sell_price), 0) FROM sale_items WHERE card_id IN ({cardPlaceholder})",
            card_ids,
        ).fetchone()[0]

        try:
            self.db.execute(
                f"UPDATE cards SET sold_date = NULL WHERE id IN ({cardPlaceholder})", card_ids
            )
            self.db.execute(f"DELETE FROM sale_items WHERE card_id IN ({cardPlaceholder})", card_ids)
        except Exception:
            self.db.rollback
            raise sqlite3.Error("Failed to update database")
        return cards_sum or 0.0

    def _return_sealed(self, sealed: list[SaleCorrectionItem]) -> float:

        sealedPlan = []
        for entry in sealed:
            sealed_id = entry.id
            returnQuantity = entry.quantity
            if not sealed_id or not returnQuantity or returnQuantity <= 0:
                continue
            row = self.db.execute(
                "SELECT quantity, market_value FROM sealed WHERE id = ?", (sealed_id,)
            ).fetchone()
            if row is None:
                self.db.rollback()
                raise ValueError(f"Sealed item {sealed_id} not found")
            if returnQuantity > row["quantity"]:
                self.db.rollback()
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
                self.db.rollback()
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
                self.db.execute(
                    "UPDATE bulk_items SET quantity = quantity + ? WHERE id = ?",
                    (bs_row["quantity"], target["id"]),
                )

    #TODO: change to DTO
    def generate_credit_note(self, sale_id: int, data: SaleCorrectionRequest) -> None:
        returned_value = self._order_return(sale_id, data.cards, data.sealed)

        creditNoteNum = None
        for attempt in range(3):
            row = self.db.execute(
                "SELECT COALESCE(MAX(record_number), 0) + 1 FROM sales_correction WHERE change_type = 'credit'"
            ).fetchone()
            creditNoteNum = row[0]
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
            pdf, cn_num = generateInvoice.generateCreditNote(
                data.get("reciever"),
                data.get("items") if data.get("items") else None,
                data.get("sealed") if data.get("sealed") else None,
                data.get("bulk"),
                data.get("holo"),
                data.get("ex"),
                None,
                data.get("shipping"),
                original_invoice_num,
                creditNoteNum,
            )
        except Exception as e:
            self.db.rollback()
            logger.critical("Credit note generation failed %s", e)
            return jsonify({"status": "error", "message": f"{str(e)}, Error code: Ax06"}), 500

        self.db.commit()
        logger.info(
            "Credit note generated succesfully | original invoice num: %s", original_invoice_num
        )
            
