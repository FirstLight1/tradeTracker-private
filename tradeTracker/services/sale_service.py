import os
import base64
import datetime
import tradeTracker.services.models as models
import tradeTracker.CONSTANTS as CONSTANTS
import json
from Crypto.Cipher import AES

if os.environ.get("FLASK_ENV") != "production":
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


class SaleService:
    def __init__(self, db, receipt_service):
        self.db = db
        self.receipt_service = receipt_service

    def process_sale(self, sale_input) -> models.SaleResult:
        try:
            self.db.execute("BEGIN IMMEDIATE")
            self._check_inventory(sale_input)
            self._prepare_cards(sale_input)
            receipt = self.receipt_service.issue(sale_input, self.db)
            sale_id = self._insert_sale_header(sale_input, receipt)
            self._insert_sale_items(sale_id, sale_input)
            return models.SaleResult(sale_id=sale_id, receipt=receipt)
        except Exception:
            self.db.rollback()
            raise

    def _check_bulk_inventory(self, db, item_type, quantity_needed):
        """Check if sufficient inventory exists for the given item type."""
        result = db.execute(
            "SELECT SUM(quantity) FROM bulk_items WHERE item_type = ?", (item_type,)
        ).fetchone()
        available = result[0] if result[0] is not None else 0
        return available >= quantity_needed

    def _check_inventory(self, sale_input):
        bulk = sale_input.bulk
        if bulk and bulk.get("quantity", 0) > 0:
            if not self._check_bulk_inventory(self.db, "bulk", bulk.get("quantity", 0)):
                raise ValueError
        holo = sale_input.holo
        if holo and holo.get("quantity", 0) > 0:
            if not self._check_bulk_inventory(self.db, "holo", holo.get("quantity", 0)):
                raise ValueError

        ex = sale_input.ex
        if ex and ex.get("quantity", 0) > 0:
            if not self._check_bulk_inventory(self.db, "ex", ex.get("quantity", 0)):
                raise ValueError

        sealed = sale_input.sealed
        if sealed:
            for item in sealed:
                name = item.get("sealedName")
                language = item.get("language", "en")
                if language not in CONSTANTS.ALLOWED_LANGUAGES:
                    raise ValueError("Invalid language code")
                try:
                    needed = int(item.get("quantity", 1))
                except (TypeError, ValueError) as error:
                    raise ValueError("Invalid sealed quantity") from error
                if needed <= 0:
                    raise ValueError("Invalid sealed quantity")
                available = self.db.execute(
                    "SELECT COALESCE(SUM(quantity), 0) FROM sealed "
                    "WHERE lower(name) = lower(?) AND language = ? "
                    "AND sale_id IS NULL AND opened = 0",
                    (name, language),
                ).fetchone()[0]
                if available < needed:
                    raise ValueError

    def _prepare_cards(self, sale_input):
        seen_ids = set()
        for card in sale_input.cards:
            card_id = card.get("cardId")
            if card_id is None or card_id in seen_ids:
                raise ValueError("Card is not available")
            seen_ids.add(card_id)

            inventory_card = self.db.execute(
                "SELECT c.card_name, c.card_num, c.condition, c.card_price, "
                "gsc.grader, gsc.grade_numeric, gsc.grade_label, gsc.qualifier, "
                "gsc.cert_number, gsc.landed_cost, gsc.submission_id, gs.status "
                "FROM cards c "
                "LEFT JOIN sale_items si ON si.card_id = c.id "
                "LEFT JOIN grading_submission_cards gsc "
                "ON gsc.card_id = c.id AND gsc.is_current = 1 "
                "LEFT JOIN grading_submissions gs ON gs.id = gsc.submission_id "
                "WHERE c.id = ? AND c.sold_date IS NULL AND si.card_id IS NULL",
                (card_id,),
            ).fetchone()
            if not inventory_card or (
                inventory_card["submission_id"] is not None
                and inventory_card["status"] != models.GradeStatus.GRADED
            ):
                raise ValueError(f"Card with id:{card_id} is not available")

            grade_parts = [
                inventory_card["grader"],
                self._format_grade(inventory_card["grade_numeric"]),
                inventory_card["grade_label"],
                inventory_card["qualifier"],
            ]
            card["cardName"] = inventory_card["card_name"]
            card["cardNum"] = inventory_card["card_num"] or ""
            card["condition"] = inventory_card["condition"]
            card["displayCondition"] = (
                " ".join(filter(None, grade_parts)) or inventory_card["condition"]
            )
            card["certNumber"] = inventory_card["cert_number"] or None
            card["internalCost"] = (
                inventory_card["landed_cost"]
                if inventory_card["landed_cost"] is not None
                else inventory_card["card_price"]
            )

    @staticmethod
    def _format_grade(grade):
        if grade is None:
            return None
        return str(int(grade)) if float(grade).is_integer() else str(grade)

    def _insert_sale_header(self, sale_input, receipt):
        shippingPrice = None
        if sale_input.shipping is not None:
            shippingPrice = sale_input.shipping.get("shippingPrice", None)

        recieverInfoJson = json.dumps(sale_input.reciever).encode("utf-8")
        key = base64.b64decode(os.environ["KEY"])
        cipher = AES.new(key, AES.MODE_GCM)
        recieverInfoCrypt, tag = cipher.encrypt_and_digest(recieverInfoJson)
        nonce = cipher.nonce

        result = {
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(recieverInfoCrypt).decode(),
            "tag": base64.b64encode(tag).decode(),
        }
        result = json.dumps(result)

        if shippingPrice == None:
            shippingPrice = 0

        sale_date = datetime.date.today().isoformat()
        total_amount = round(float(sale_input.reciever.get("total")) + float(shippingPrice), 2)
        invoice_num = receipt.number

        idOrder = None if sale_input.idOrder is None else str(sale_input.idOrder)

        cursor = self.db.execute(
            "INSERT INTO sales (invoice_number, sale_date, total_amount, notes, shipping_info, idOrder) VALUES (?, ?, ?, ?, ?, ?)",
            (invoice_num, sale_date, total_amount, result, shippingPrice, idOrder),
        )

        sale_id = cursor.lastrowid
        return sale_id

    def _insert_sale_items(self, sale_id, sale_input):
        cards = sale_input.cards
        sale_date = datetime.date.today().isoformat()
        if len(cards) > 0:
            for card in cards:
                sell_price = float(card.get("marketValue", 0))
                updated = self.db.execute(
                    "UPDATE cards SET sold_date = ? WHERE id = ? AND sold_date IS NULL "
                    "AND NOT EXISTS (SELECT 1 FROM sale_items WHERE card_id = ?) "
                    "AND NOT EXISTS ("
                    "SELECT 1 FROM grading_submission_cards gsc "
                    "JOIN grading_submissions gs ON gs.id = gsc.submission_id "
                    "WHERE gsc.card_id = cards.id AND gsc.is_current = 1 "
                    "AND gs.status != ?)",
                    (sale_date, card.get("cardId"), card.get("cardId"), models.GradeStatus.GRADED),
                )
                if updated.rowcount != 1:
                    raise ValueError(f"Card with id:{card.get('cardId')} is not available")

                self.db.execute(
                    "INSERT INTO sale_items "
                    "(sale_id, card_id, sell_price, profit, internal_cost, internal_profit) "
                    "VALUES (?, ?, ?, ? - (SELECT card_price FROM cards WHERE id = ?), ?, ? - ?)",
                    (
                        sale_id,
                        card.get("cardId"),
                        sell_price,
                        sell_price,
                        card.get("cardId"),
                        card.get("internalCost"),
                        sell_price,
                        card.get("internalCost"),
                    ),
                )
        sealed = sale_input.sealed
        if sealed:
            for item in sealed:
                self._deduct_sealed_fifo(
                    item.get("sealedName"),
                    item.get("language", "en"),
                    int(item.get("quantity", 1)),
                    sale_id,
                    float(item.get("marketValue") or 0),
                )

        bulk = sale_input.bulk
        if bulk:
            self.db.execute(
                "INSERT INTO bulk_sales (sale_id, item_type, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)",
                (
                    sale_id,
                    "bulk",
                    bulk.get("quantity", 0),
                    bulk.get("unit_price", CONSTANTS.BULK_ITEM_UNIT_PRICES["bulk"]),
                    bulk.get("sell_price", 0),
                ),
            )
            # I am pretty sure the execudes are not needed
            self.db.execute(
                'UPDATE bulk_counter SET counter = counter - ? WHERE counter_name = "bulk"',
                (bulk.get("quantity", 0),),
            )
            # Deduct from bulk_items using FIFO
            self._deduct_bulk_items_fifo("bulk", bulk.get("quantity", 0))

        holo = sale_input.holo
        if holo:
            self.db.execute(
                "INSERT INTO bulk_sales (sale_id, item_type, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)",
                (
                    sale_id,
                    "holo",
                    holo.get("quantity", 0),
                    holo.get("unit_price", CONSTANTS.BULK_ITEM_UNIT_PRICES["holo"]),
                    holo.get("sell_price", 0),
                ),
            )
            self.db.execute(
                'UPDATE bulk_counter SET counter = counter - ? WHERE counter_name = "holo"',
                (holo.get("quantity", 0),),
            )
            # Deduct from bulk_items using FIFO
            self._deduct_bulk_items_fifo("holo", holo.get("quantity", 0))

        ex = sale_input.ex
        if ex:
            self.db.execute(
                "INSERT INTO bulk_sales (sale_id, item_type, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)",
                (
                    sale_id,
                    "ex",
                    ex.get("quantity", 0),
                    ex.get("unit_price", CONSTANTS.BULK_ITEM_UNIT_PRICES["ex"]),
                    ex.get("sell_price", 0),
                ),
            )
            self.db.execute(
                'UPDATE bulk_counter SET counter = counter - ? WHERE counter_name = "ex"',
                (ex.get("quantity", 0),),
            )
            self._deduct_bulk_items_fifo("ex", ex.get("quantity", 0))

    def _deduct_bulk_items_fifo(self, item_type, quantity_to_deduct):
        """Deduct bulk/holo items using FIFO (First In, First Out) from auctions."""
        remaining = quantity_to_deduct

        # Get all bulk_items for this type, ordered by auction_id (FIFO)
        items = self.db.execute(
            "SELECT id, auction_id, quantity FROM bulk_items "
            "WHERE item_type = ? ORDER BY auction_id ASC",
            (item_type,),
        ).fetchall()

        for item in items:
            if remaining <= 0:
                break

            item_id = item["id"]
            current_quantity = item["quantity"]

            if current_quantity <= remaining:
                # Delete this item entirely
                self.db.execute("DELETE FROM bulk_items WHERE id = ?", (item_id,))
                remaining -= current_quantity
            else:
                # Reduce quantity
                new_quantity = current_quantity - remaining
                self.db.execute(
                    "UPDATE bulk_items SET quantity = ?, total_price = quantity * unit_price "
                    "WHERE id = ?",
                    (new_quantity, item_id),
                )
                remaining = 0

    def _deduct_sealed_fifo(self, name, language, sell_qty, sale_id, sell_price=None):
        """Deduct sealed units for a product using FIFO (oldest rows first).

        When a row is only partially sold it is split: the inventory row's
        quantity is reduced and a new row carrying the sold units (with the
        same per-unit price/market_value, purchase date and auction) is
        inserted against this sale, so reports stay accurate per source row.
        """
        from tradeTracker.actions import normalize

        remaining = sell_qty

        rows = self.db.execute(
            "SELECT id, name, language, quantity, price, market_value, date, auction_id, "
            "cardMarketID FROM sealed "
            "WHERE lower(name) = lower(?) AND language = ? AND sale_id IS NULL "
            "AND opened = 0 ORDER BY id ASC",
            (name, language),
        ).fetchall()

        for row in rows:
            if remaining <= 0:
                break

            if row["quantity"] <= remaining:
                # Whole row consumed - attach it to this sale (keeps its quantity)
                self.db.execute(
                    "UPDATE sealed SET sale_id = ?, sell_price = ? WHERE id = ?",
                    (sale_id, sell_price, row["id"]),
                )
                remaining -= row["quantity"]
            else:
                # Partial - shrink the inventory row and record the sold units
                self.db.execute(
                    "UPDATE sealed SET quantity = quantity - ? WHERE id = ?",
                    (remaining, row["id"]),
                )
                self.db.execute(
                    "INSERT INTO sealed(name, normalized_name, language, quantity, price, "
                    "market_value, sell_price, date, auction_id, sale_id, cardMarketID) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row["name"],
                        normalize(row["name"]),
                        language,
                        remaining,
                        row["price"],
                        row["market_value"],
                        sell_price,
                        row["date"],
                        row["auction_id"],
                        sale_id,
                        row["cardMarketID"],
                    ),
                )
                remaining = 0
