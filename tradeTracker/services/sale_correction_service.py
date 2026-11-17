import json
from typing import Any
from io import BytesIO
import sqlite3

from tradeTracker.services.models import SaleCorrectionItem

class SaleCorrectionService:
    def __init__(self, db):
        self.db = db

    def _order_return(self,sale_id:int, items: dict[str, list[SaleCorrectionItem]], shipping_value: float = 0) -> float:
        #TODO: when cards and sealed DTO exist
        returned_value = 0.0
        if "card_ids" in items:
            returned_value += self._return_cards(sale_id, items['card_ids'])

        if "sealed" in items:
            returned_value += self._return_sealed(sale_id, items['sealed'])


        raise NotImplementedError

    def _return_cards(self, sale_id: int, cards: list[SaleCorrectionItem]) -> float:
        cardPlaceholder = ",".join("?" for _ in cards)
        card_ids = [card.card_id for card in cards]
    
        cards_sum= self.db.execute(
            f"SELECT COALESCE(SUM(sell_price), 0) FROM sale_items WHERE card_id IN ({cardPlaceholder})",
            card_ids,
        ).fetchone()[0]

        try:
            self.db.execute(
                f"UPDATE cards SET sold_date = NULL WHERE id IN ({cardPlaceholder})", card_ids
            )
            self.db.execute(f"DELETE FROM sale_items WHERE card_id IN ({cardPlaceholder})", card_ids)
        except sqlite3.Error:
            raise sqlite3.Error("Failed to update database")
        return cards_sum or 0.0

    def _return_sealed(self, sale_id: int, sealed: list[SaleCorrectionItem]) -> float:



        raise NotImplementedError

    #TODO: change to DTO
    def generate_credit_note(self, sale_id: int, items: dict[str,Any]) -> None:
        returned_value = self._order_return(sale_id, items)

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
            
