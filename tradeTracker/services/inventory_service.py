import logging

from tradeTracker.services.models import InventoryWriteOff, AuctionInput, ItemInput, EditModel
import tradeTracker.CONSTANTS as CONSTANTS


class InventoryService:
    def __init__(self, db):
        self.db = db


    def create_auction(self, auction: AuctionInput) -> int:
        try:
            self.db.execute("INSERT INTO auctions (auction_name, auction_price, date_created, payment_method) VALUES (?,?,?,?)",
                (auction.name, auction.buy_price, auction.date, auction.payments))
            self.db.commit()
            return self.db.lastrowid
        except Exception as e:
            self.db.rollback()
            logging.exception("Failed to create auction | %s", e)
            raise Exception("Failed to create auction")

    def delete_auction(self, auction_id: int) -> None:
        try:
            self.db.execute("DELETE FROM auctions WHERE id = ?", (auction_id,))
            self.db.execute("DELETE FROM cards WHERE auction_id = ?", (auction_id,))
            self.db.execute("DELETE FROM sealed WHERE auction_id = ?", (auction_id,))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logging.exception("Failed to delete auction | %s", e)
            raise Exception("Failed to delete auction")

    def update_auction(self, auction_id: int, auction: EditModel) -> None:
        if auction.field not in CONSTANTS.AUCTION_ALLOWED_FIELDS:
            raise ValueError(f"Invalid field: {auction.field}")

        try:
            self.db.execute(f"UPDATE auctions SET {auction.field} = ? WHERE id = ?", (auction.value, auction_id))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logging.exception("Failed to update auction | %s", e)
            raise Exception("Failed to update auction")

    def merge_auctions(self, auction_id: int, target_id: int) -> None:
        try:
            self.db.execute(
                "UPDATE auctions SET auction_price = auction_price + (SELECT auction_price FROM auctions WHERE id = ?) WHERE id = ?",
                (auction_id, target_id),
            )
            self.db.execute("UPDATE cards SET auction_id = ? WHERE auction_id = ?", (target_id, auction_id))
            self.db.execute("UPDATE sealed SET auction_id = ? WHERE auction_id = ?", (target_id, auction_id))
            self.db.execute(
                "UPDATE bulk_items SET auction_id = ? WHERE auction_id = ?", (target_id, auction_id)
            )
            self.db.execute("DELETE FROM auctions WHERE id = ?", (auction_id,))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logging.exception(f"Error merging auctions | {e}")
            raise Exception("Failed to merge auctions")

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
