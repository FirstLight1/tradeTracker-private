import logging
from typing import Any
from tradeTracker.services.models import InventoryWriteOff, AuctionInput, ItemInput, EditModel, GradeStatus
from tradeTracker.utils.cardmarket import resolve_cardmarket_id_model
import tradeTracker.CONSTANTS as CONSTANTS
import tradeTracker.utils.formating as formating


class InventoryService:
    def __init__(self, db):
        self.db = db 
        
    def load_auctions(self) -> list[dict[str, Any]]:
        rows = self.db.execute("""
            SELECT
                a.*,
                b.sale_id,
                s.invoice_number
            FROM auctions AS a
            LEFT JOIN barter AS b
                ON b.auction_id = a.id
            LEFT JOIN sales AS s
                ON s.id = b.sale_id
            WHERE
                a.id = 1
                OR EXISTS (
                    SELECT 1
                    FROM cards AS c
                    WHERE c.auction_id = a.id
                    AND c.sold_date IS NULL
                    AND c.disposal_reason IS NULL
                    AND NOT EXISTS (
                        SELECT 1
                        FROM sale_items AS si
                        WHERE si.card_id = c.id
                    )
                )
            ORDER BY
                CASE WHEN a.id = 1 THEN 0 ELSE 1 END,
                a.id DESC;
                """).fetchall()
        return [dict(row) for row in rows]

    def load_purchases(self) -> list[dict[str, Any]]:
        rows = self.db.execute("""
            SELECT
                *
            FROM auctions
            ORDER BY
                id DESC;
            """).fetchall()
        return [dict(row) for row in rows]

    def create_auction_with_items(self, auction: AuctionInput, items: list[ItemInput]) -> int:
        try:
            auction_id = self._create_auction(auction)
            self._insert_items(items, auction_id)
            self.db.commit()
            return auction_id
        except Exception as e:
            self.db.rollback()
            logging.exception("Failed to create auction | %s", e)
            raise Exception("Failed to create auction")

    def _create_auction(self, auction: AuctionInput) -> int:
        try:
            cur = self.db.cursor()
            cur.execute("INSERT INTO auctions (auction_name, auction_price, date_created, payment_method) VALUES (?,?,?,?)",
                (auction.name, auction.buy_price, auction.date, auction.payments))
            return cur.lastrowid
        except Exception as e:
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
            
        #TODO: add date_created
        
        if auction.field == "date_created":
            try:
                value = formating.parse_date_to_iso(auction.value)
            except ValueError as e:
                raise ValueError(f"Invalid date format: {value!r}. Expected ISO 8601, YYYY-MM-DD, or dd-mm-yyyy.")
        else:
            value = auction.value
                

        try:
            self.db.execute(f"UPDATE auctions SET {auction.field} = ? WHERE id = ?", (value, auction_id))
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

    def load_items(self, auction_id: int | None, filter: str = 'sold') -> list[dict[str, Any]]:
        #TODO: rename the filter cause this is not sold items
        if filter == "sold":
            cardFilter = "c.sold_date IS NULL AND si.card_id IS NULL AND c.disposal_reason IS NULL"
            sealedFilter = "sale_id IS NULL AND opened = 0 AND disposal_reason IS NULL"
        elif filter == "all":
            cardFilter = "1=1"
            sealedFilter = "1=1"
        else:
            raise ValueError(f"Invalid filter: {filter}")

        if auction_id is not None:
            cardRows = self.db.execute(f"""
                SELECT c.*,"card" as item_type, gsc.grader, gsc.grade_numeric, gsc.grade_label, gsc.qualifier, gsc.cert_number
                FROM cards AS c
                LEFT JOIN sale_items AS si
                    ON c.id = si.card_id
                LEFT JOIN grading_submission_cards AS gsc
                    ON c.id = gsc.card_id
                    AND gsc.is_current = 1
                WHERE c.auction_id = ?
                AND {cardFilter}
                """,(auction_id,)).fetchall()
            sealedRows = self.db.execute(f"""
                SELECT *, "sealed" as item_type
                FROM sealed
                WHERE auction_id = ?
                AND {sealedFilter}
                """,(auction_id,)).fetchall()
            items =  cardRows + sealedRows
            return [dict(row) for row in items]
        else:
            rows = self.db.execute(f"""
            SELECT *, "sealed" as item_type
            FROM sealed
            WHERE {sealedFilter}
            AND auction_id IS NULL
            """).fetchall()
            return [dict(row) for row in rows]
                                    

    def _insert_items(self, items: list[ItemInput], auction_id: int) -> None:
        cards_to_add = []
        sealed_to_add = []
        for item in items:
            if item.item_type == "card":
                for _ in range(item.quantity):
                    to_add = (
                        item.name,
                        item.normalized_name,
                        item.number,
                        item.condition,
                        item.lang,
                        item.buy_price,
                        item.market_value,
                        resolve_cardmarket_id_model(self.db, item, "name", "card_num"),
                        auction_id,
                    )
                    cards_to_add.append(to_add)
            elif item.item_type == "sealed":
                to_add = (
                    item.name,
                    item.normalized_name,
                    item.quantity,
                    item.lang,
                    item.buy_price,
                    item.market_value,
                    item.date,
                    resolve_cardmarket_id_model(self.db, item, "name", "card_num"),
                    auction_id,
                )
                sealed_to_add.append(to_add)
            else:
                raise ValueError(f"Invalid item type: {item.item_type}")

        try:
            self.db.executemany(
                "INSERT INTO cards (card_name, normalized_name, card_num, condition, language, card_price, market_value, cardmarketId, auction_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                cards_to_add,
            )
            self.db.executemany(
                "INSERT INTO sealed (name, normalized_name, quantity, language, price, market_value, date, cardmarketId, auction_id) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                sealed_to_add,
            )
        except Exception as e:
            raise Exception("Failed to add items")

    def add_items_to_auction(self, auction_id: int, items: list[ItemInput]) -> None:
        try:
            self._insert_items(items, auction_id)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logging.exception("Failed to add items | %s", e)
            raise Exception("Failed to add items")

    def delete_item(self, item_id: int, item_type: str) -> None:
        if item_type == "card":
            try:
                self.db.execute("DELETE FROM cards WHERE id = ?", (item_id,))
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                logging.error(f"Error deleting card {item_id}: {e}")
                raise Exception("Failed to delete card")
        elif item_type == "sealed":
            try:
                self.db.execute("DELETE FROM sealed WHERE id = ?", (item_id,))
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                logging.error(f"Error deleting sealed {item_id}: {e}")
                raise Exception("Failed to delete sealed")
        else:
            raise ValueError(f"Invalid item type: {item_type}")

    def update_item(self, item_id: int, item: EditModel, item_type: str) -> None:
        if item.field not in CONSTANTS.ITEM_ALLOWED_FIELDS:
            raise ValueError(f"Invalid field: {item.field}")

        if item_type == "card":
            try:
                self.db.execute(f"UPDATE cards SET {item.field} = ? WHERE id = ?", (item.value, item_id))
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                logging.exception(f"Failed to update card {item_id} | {e}")
                raise Exception("Failed to update card")
        elif item_type == "sealed":
            try:
                self.db.execute(f"UPDATE sealed SET {item.field} = ? WHERE id = ?", (item.value, item_id))
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                logging.exception(f"Failed to update sealed {item_id} | {e}")
                raise Exception("Failed to update sealed")
        else:
            raise ValueError(f"Invalid item type: {item_type}")

    def mark_sealed_opened(self, sealed_id: int, auction_id: int | None = None) -> int:
        try:
            cur = self.db.cursor()
            row = cur.execute(
                "SELECT * FROM sealed WHERE id = ? AND sale_id IS NULL AND opened = 0 AND disposal_reason IS NULL",
                (sealed_id,),
            ).fetchone()
            if row["quantity"] == 1:
                cur.execute(
                    "UPDATE sealed SET opened = 1 WHERE id = ?",
                    (sealed_id,),
                )
                return sealed_id
            else:
                cur.execute(
                    "UPDATE sealed SET quantity = quantity - 1 WHERE id = ?",
                    (sealed_id,),
                )
                cur.execute(
                    "INSERT INTO sealed (name, normalized_name, language, price, market_value, date, cardmarketId, auction_id, opened) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["name"],
                        formating.normalize(row["name"]),
                        row["language"],
                        row["price"],
                        row["market_value"],
                        row["date"],
                        row["cardmarketId"],
                        auction_id if auction_id is not None else None,
                        1,
                    ),
                )
                return cur.lastrowid
        except Exception as e:
            raise Exception(f"Error opening sealed item | {e}")

    def get_sellable_card(self, card_id: int) -> dict[str, Any]:
        card = self.db.execute("""
                SELECT c.card_name, c.card_num, c.condition, c.card_price, 
                gsc.grader, gsc.grade_numeric, gsc.grade_label, gsc.qualifier, 
                gsc.cert_number, gsc.landed_cost, gsc.submission_id, gs.status 
                FROM cards c 
                LEFT JOIN sale_items si ON si.card_id = c.id 
                LEFT JOIN grading_submission_cards gsc 
                ON gsc.card_id = c.id AND gsc.is_current = 1 
                LEFT JOIN grading_submissions gs ON gs.id = gsc.submission_id 
                WHERE c.id = ? AND c.sold_date IS NULL AND si.card_id IS NULL 
                AND c.disposal_reason IS NULL 
                AND NOT EXISTS (
                    SELECT 1
                    FROM grading_submission_cards gsc2
                    JOIN grading_submissions gs2 ON gs2.id = gsc2.submission_id
                    WHERE gsc2.card_id = c.id
                    AND gsc2.is_current = 1
                    AND gs2.status IN ('submitted', 'grading')
                )
                """,
                (card_id,),
            ).fetchone()
        if not card or (
            card["submission_id"] is not None
            and card["status"] != GradeStatus.GRADED
        ):
            raise ValueError(f"Card with id:{card_id} is not available")
        return dict(card)

    def mark_sold_card(self, card_id: int, sale_date: str) -> None:
        try:
            self.db.execute("UPDATE cards SET sold_date = ? WHERE id = ?", (sale_date, card_id))
        except ValueError as e:
            raise ValueError(f"Card with id:{card_id} is not available")
        except Exception as e:
            raise Exception(f"Error marking card as sold | {e}")

    def allocate_sealed_to_sale(
        self,
        name: str,
        language: str,
        quantity: int,
        sale_id: int,
        sell_price: float,
    ) -> None:
        if quantity <= 0:
            raise ValueError("Sealed quantity must be greater than zero")

        rows = self.db.execute(
            "SELECT id, quantity FROM sealed "
            "WHERE lower(name) = lower(?) AND language = ? AND sale_id IS NULL "
            "AND opened = 0 AND disposal_reason IS NULL ORDER BY id ASC",
            (name, language),
        ).fetchall()
        if sum(row["quantity"] for row in rows) < quantity:
            raise ValueError("Sealed item is not available in the requested quantity")

        remaining = quantity
        for row in rows:
            if remaining == 0:
                break
            allocated = min(row["quantity"], remaining)
            self.allocate_sealed_row_to_sale(
                row["id"], allocated, sale_id, sell_price
            )
            remaining -= allocated

    def allocate_sealed_row_to_sale(
        self,
        sealed_id: int,
        quantity: int,
        sale_id: int,
        sell_price: float,
    ) -> None:
        if quantity <= 0:
            raise ValueError("Sealed quantity must be greater than zero")

        row = self.db.execute(
            "SELECT quantity FROM sealed WHERE id = ? AND sale_id IS NULL "
            "AND opened = 0 AND disposal_reason IS NULL",
            (sealed_id,),
        ).fetchone()
        if row is None or quantity > row["quantity"]:
            raise ValueError("Sealed item is not available in the requested quantity")

        if quantity == row["quantity"]:
            updated = self.db.execute(
                "UPDATE sealed SET sale_id = ?, sell_price = ? "
                "WHERE id = ? AND quantity = ? AND sale_id IS NULL "
                "AND opened = 0 AND disposal_reason IS NULL",
                (sale_id, sell_price, sealed_id, quantity),
            )
            if updated.rowcount != 1:
                raise ValueError("Sealed item is no longer available")
            return

        updated = self.db.execute(
            "UPDATE sealed SET quantity = quantity - ? "
            "WHERE id = ? AND quantity > ? AND sale_id IS NULL "
            "AND opened = 0 AND disposal_reason IS NULL",
            (quantity, sealed_id, quantity),
        )
        if updated.rowcount != 1:
            raise ValueError("Sealed item is no longer available")

        self.db.execute(
            "INSERT INTO sealed (name, normalized_name, quantity, language, price, "
            "market_value, sell_price, date, sale_id, auction_id, opened, cardMarketID) "
            "SELECT name, normalized_name, ?, language, price, market_value, ?, date, "
            "?, auction_id, 0, cardMarketID FROM sealed WHERE id = ?",
            (quantity, sell_price, sale_id, sealed_id),
        )

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
