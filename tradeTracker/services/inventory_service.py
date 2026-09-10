import logging

from tradeTracker.services.models import InventoryWriteOff


class InventoryService:
    def __init__(self, db):
        self.db = db

    def item_writeoff(self, writeoff: InventoryWriteOff) -> None:
        try:
            if writeoff.item_type == "card":
                updated = self.db.execute(
                    "UPDATE cards SET disposal_reason = ?, disposal_date = ?, disposal_note = ? "
                    "WHERE id = ? AND sold_date IS NULL AND disposal_reason IS NULL "
                    "AND NOT EXISTS (SELECT 1 FROM sale_items WHERE card_id = cards.id) "
                    "AND NOT EXISTS ("
                    "SELECT 1 FROM grading_submission_cards gsc "
                    "JOIN grading_submissions gs ON gs.id = gsc.submission_id "
                    "WHERE gsc.card_id = cards.id AND gsc.is_current = 1 "
                    "AND gs.status != 'graded')",
                    (
                        writeoff.disposal_reason,
                        writeoff.disposal_date,
                        writeoff.disposal_note,
                        writeoff.item_id,
                    ),
                )
                if updated.rowcount != 1:
                    raise ValueError("Card is not available to write off")
            else:
                self._writeoff_sealed(writeoff)

            self.db.commit()
        except Exception:
            self.db.rollback()
            logging.exception(
                "Failed to write off %s %s", writeoff.item_type, writeoff.item_id
            )
            raise

    def _writeoff_sealed(self, writeoff: InventoryWriteOff) -> None:
        row = self.db.execute(
            "SELECT quantity FROM sealed WHERE id = ? AND sale_id IS NULL "
            "AND opened = 0 AND disposal_reason IS NULL",
            (writeoff.item_id,),
        ).fetchone()
        if row is None or writeoff.quantity > row["quantity"]:
            raise ValueError("Sealed item is not available in the requested quantity")

        if writeoff.quantity == row["quantity"]:
            updated = self.db.execute(
                "UPDATE sealed SET disposal_reason = ?, disposal_date = ?, disposal_note = ? "
                "WHERE id = ? AND quantity = ? AND sale_id IS NULL AND opened = 0 "
                "AND disposal_reason IS NULL",
                (
                    writeoff.disposal_reason,
                    writeoff.disposal_date,
                    writeoff.disposal_note,
                    writeoff.item_id,
                    writeoff.quantity,
                ),
            )
            if updated.rowcount != 1:
                raise ValueError("Sealed item is no longer available")
            return

        updated = self.db.execute(
            "UPDATE sealed SET quantity = quantity - ? "
            "WHERE id = ? AND quantity > ? AND sale_id IS NULL AND opened = 0 "
            "AND disposal_reason IS NULL",
            (writeoff.quantity, writeoff.item_id, writeoff.quantity),
        )
        if updated.rowcount != 1:
            raise ValueError("Sealed item is no longer available")

        self.db.execute(
            "INSERT INTO sealed (name, normalized_name, quantity, language, price, "
            "market_value, date, auction_id, opened, cardMarketID, disposal_reason, "
            "disposal_date, disposal_note) "
            "SELECT name, normalized_name, ?, language, price, market_value, date, "
            "auction_id, 0, cardMarketID, ?, ?, ? FROM sealed WHERE id = ?",
            (
                writeoff.quantity,
                writeoff.disposal_reason,
                writeoff.disposal_date,
                writeoff.disposal_note,
                writeoff.item_id,
            ),
        )

    def undo_item_writeoff(self, item_id: int, item_type: str) -> None:
        if item_type == "card":
            try:
                self.db.execute(
                    "UPDATE cards SET disposal_reason = NULL, disposal_date = NULL, disposal_note = NULL "
                    "WHERE id = ? AND disposal_reason IS NOT NULL",
                    (item_id,),
                )
            except Exception as e:
                self.db.rollback()
                logging.error(f"Error undoing write off for card {item_id}: {e}")
                raise Exception("Failed to undo write off")
        elif item_type == "sealed":
            try:
                self.db.execute(
                    "UPDATE sealed SET disposal_reason = NULL, disposal_date = NULL, disposal_note = NULL "
                    "WHERE id = ? AND disposal_reason IS NOT NULL",
                    (item_id,),
                )
            except Exception as e:
                self.db.rollback()
                logging.error(f"Error undoing write off for sealed {item_id}: {e}")
                raise Exception("Failed to undo write off")

        self.db.commit()
