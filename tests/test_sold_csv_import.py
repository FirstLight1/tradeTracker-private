"""
End-to-end test for the `sold` branch of importCSV() (tradeTracker/actions.py).

The dev DB lacks the cards/sealed rows whose `cardMarketID` the uploaded
articles reference, so this builds its own temp DB and crafts minimal
orders/articles CSVs that exercise:

  * _fixArticlesUpload()  (location-JSON stripping)
  * article expansion by the `items` count
  * orders<->articles merge and the cardmarketId + _match_seq DB match
  * complete-vs-rejected order grouping
  * the per-order SaleService.process_sale() loop (invoice + DB writes)
  * the zip / one-shot download token handoff

Orders covered:
  1001  complete, mixed  : 1 card + a 2-unit card line (expansion) + 1 sealed
  1002  rejected         : references a cardMarketID not present in inventory
  1003  complete, card   : single card
"""

import io
import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tradeTracker import create_app
from tradeTracker.db import get_db
from tradeTracker.actions import normalize


ORDERS_HEADER = (
    "idOrder,customer,status,dateBought,datePaid,dateSent,dateReceived,"
    "shippingMethod,trackingNumber,temporaryEmail,isPresale,shippingAddressName,"
    "shippingAddressExtra,shippingAddressStreet,shippingAddressCity,"
    "shippingAddressZip,shippingAddressCountry,phone,buyerVAT,updatedAt,"
    "articleCategories,articles,articleValue,shippingValue,totalValue,"
    "currencyCode,note,PID,issues"
)

ARTICLES_HEADER = (
    "idOrder,customer,status,pos,items,category,expansion,name,language,"
    "condition,price,comments,finishType,isSigned,isPlayset,isAltered,issues,"
    "location,boughtAt,cardmarketId"
)

# A realistic location blob; _fixArticlesUpload() must strip it before pandas
# parses the CSV (otherwise the embedded quotes/commas break the row).
LOC = '"{"locationName":"Many more cards available!","locationQuantity":0}"'


def _order_row(idOrder, name, article_value, shipping_value):
    total_value = float(article_value) + float(shipping_value)
    return (
        f'"{idOrder}","Buyer ({name})","sent","2026-05-31T07:44:55.000Z",'
        f'"2026-05-31T07:45:02.000Z","2026-06-03T21:07:25.000Z","","Letter","","",'
        f'"false","{name}","","Hlavna 1","Bratislava","85104","SK","","",'
        f'"03.06.2026 23:07","Pokemon Single","1","{article_value}","{shipping_value}",'
        f'"{total_value:.2f}","EUR","","",""'
    )


def _article_row(idOrder, name, pos, items, price, cmid):
    return (
        f'"{idOrder}","Buyer","sent","{pos}","{items}","","Paldea Evolved",'
        f'"{name}","English","NM","{price}","comment","Regular","false","","","",'
        f'{LOC},"2026-05-31T07:44:55.000Z","{cmid}"'
    )


def _orders_csv():
    rows = [
        ORDERS_HEADER,
        _order_row(1001, "Alice Smith", "10.00", "2.80"),
        _order_row(1002, "Bob Jones", "3.00", "2.80"),
        _order_row(1003, "Cara Diaz", "4.00", "2.80"),
    ]
    return "\n".join(rows).encode("utf-8")


def _articles_csv():
    rows = [
        ARTICLES_HEADER,
        # Order 1001 - everything matchable
        _article_row(1001, "Cetoddle", "1/4", 1, "1.50 €", 900001),
        _article_row(1001, "Frigibax", "2/4", 2, "2.00 €", 900002),  # 2 units -> expansion
        _article_row(1001, "Booster Bundle", "3/4", 1, "5.00 €", 900003),  # sealed
        # Order 1002 - cmid 900099 not in inventory -> rejected
        _article_row(1002, "Unknown Card", "1/1", 1, "3.00 €", 900099),
        # Order 1003 - single matchable card
        _article_row(1003, "Pikachu", "1/1", 1, "4.00 €", 900004),
    ]
    return "\n".join(rows).encode("utf-8")


class SoldCSVImportTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": self.db_path,
                "WTF_CSRF_ENABLED": False,
            }
        )
        with self.app.app_context():
            self._seed()
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _seed(self):
        db = get_db()
        db.execute('INSERT INTO auctions (id, auction_name, auction_price) VALUES (2, "A2", 50.0)')

        def add_card(cmid, name, num, price, mv):
            db.execute(
                "INSERT INTO cards (auction_id, card_name, normalized_name, card_num, condition, "
                "card_price, market_value, cardMarketID) VALUES (2,?,?,?,?,?,?,?)",
                (name, normalize(name), num, "NM", price, mv, str(cmid)),
            )

        add_card(900001, "Cetoddle", "1", 1.0, 1.5)
        # Two copies for the 2-unit (items=2) article line -> tests _match_seq
        add_card(900002, "Frigibax", "2", 1.5, 2.0)
        add_card(900002, "Frigibax", "2", 1.5, 2.0)
        add_card(900004, "Pikachu", "58", 3.0, 4.0)

        # Sealed product matched by cardMarketID; FIFO/inventory check is by name.
        db.execute(
            "INSERT INTO sealed (name, normalized_name, quantity, price, market_value, date, "
            'auction_id, cardMarketID) VALUES (?, ?, 3, 4.0, 5.0, "2026-01-01", 2, "900003")',
            ("Booster Bundle", normalize("Booster Bundle")),
        )
        db.commit()

    def _post(self):
        data = {
            "type": "sold",
            "csv-upload": [
                (io.BytesIO(_orders_csv()), "orders-test.csv"),
                (io.BytesIO(_articles_csv()), "articles-test.csv"),
            ],
        }
        # Talisman forces HTTPS; drive the client over https to avoid a 302.
        return self.client.post(
            "/importCSV",
            data=data,
            content_type="multipart/form-data",
            base_url="https://localhost",
        )

    # PacketaService is disabled in actions.py (commented out), so there is
    # nothing left to patch for it here.
    @patch("tradeTracker.actions.EPHService")
    def test_sold_import_end_to_end(self, mock_eph_service):
        # Stub the carrier services so the test does not hit live APIs.
        mock_eph = MagicMock()
        mock_eph.createSheet.return_value = "sheet-1"
        mock_eph.addParcel.return_value = {"id": "parcel-1"}

        def _fake_download_label(parcel_id, sheet_id, filename):
            return MagicMock(filename=f"label_{filename}", bytes=b"%PDF-fake")

        mock_eph.download_label.side_effect = _fake_download_label
        mock_eph_service.return_value = mock_eph

        resp = self._post()
        body = resp.get_json()
        print("\nRESPONSE", resp.status_code, json.dumps(body, indent=2, default=str))

        self.assertEqual(resp.status_code, 200, body)
        self.assertEqual(body["status"], "success")

        # --- rejected: order 1002 only, complete orders excluded ---
        rejected_ids = {int(r["idOrder"]) for r in body["rejected"]}
        self.assertEqual(rejected_ids, {1002})

        # --- failed: none of the complete orders should error ---
        self.assertEqual(body["failed"], [])

        # --- a download was produced for the completed invoices ---
        self.assertIsNotNone(body["download_url"])

        with self.app.app_context():
            db = get_db()
            # Two sales (orders 1001 and 1003), each with a fresh invoice number.
            sales = db.execute(
                "SELECT invoice_number, total_amount FROM sales ORDER BY id"
            ).fetchall()
            self.assertEqual(len(sales), 2)

            # Order 1001: 1 + 2 = 3 cards sold; Order 1003: 1 card sold => 4 sale_items.
            n_items = db.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0]
            self.assertEqual(n_items, 4)

            # All four sold cards now carry a sold_date.
            sold_cards = db.execute(
                "SELECT COUNT(*) FROM cards WHERE sold_date IS NOT NULL"
            ).fetchone()[0]
            self.assertEqual(sold_cards, 4)

            # Sealed "Booster Bundle": 1 unit deducted via FIFO and attached to a sale.
            sold_sealed = db.execute(
                "SELECT COALESCE(SUM(quantity),0) FROM sealed WHERE sale_id IS NOT NULL"
            ).fetchone()[0]
            self.assertEqual(sold_sealed, 1)
            remaining_sealed = db.execute(
                "SELECT COALESCE(SUM(quantity),0) FROM sealed WHERE sale_id IS NULL"
            ).fetchone()[0]
            self.assertEqual(remaining_sealed, 2)

        # --- the one-shot download link serves a zip and then 404s ---
        token = body["download_url"].rsplit("/", 1)[-1]
        dl = self.client.get(f"/download/{token}", base_url="https://localhost")
        self.assertEqual(dl.status_code, 200)
        self.assertEqual(dl.mimetype, "application/zip")
        self.assertEqual(
            self.client.get(f"/download/{token}", base_url="https://localhost").status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
