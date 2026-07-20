"""
Test the `inventory` branch of importCSV() (tradeTracker/actions.py).

Builds a temp DB and uploads a comma-separated CardMarket inventory CSV that
contains both card rows and a sealed-product row, then asserts:

  * cards are inserted into the `cards` table
  * sealed products are inserted into the `sealed` table
  * the created auction price matches the expected total buy price
"""
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tradeTracker import create_app
from tradeTracker.db import get_db, init_db


# Real CardMarket inventory export header (comma-separated)
CSV_HEADER = (
    "cardmarketId,quantity,name,set,setCode,cn,condition,language,"
    "isFirstEd,isReverseHolo,isSigned,finishType,oldPrice,price,comment,"
    "location,nameDE,nameES,nameFR,nameIT,rarity,listedAt"
)


def _csv_row(cmid, qty, name, set_name, set_code, cn, condition, price, listed_at):
    empty = ""
    return (
        f"{cmid},{qty},{name},{set_name},{set_code},{cn},{condition},"
        f"{empty},{empty},{empty},{empty},{empty},{empty},{price},"
        f"{empty},{empty},{empty},{empty},{empty},{empty},{empty},{listed_at}"
    )


def _inventory_csv():
    rows = [
        CSV_HEADER,
        # Card rows
        _csv_row("900001", "1", "Pikachu", "Scarlet & Violet", "SVI", "58", "NM", "4.00", "07-06-2026 09:42:30"),
        _csv_row("900002", "2", "Cetoddle", "Paldea Evolved", "PAL", "1", "NM", "1.50", "08-06-2026 10:30:00"),
        # Sealed product row (empty card number)
        _csv_row("900003", "1", "Chaos Rising Pokemon Center Elite Trainer Box", "Chaos Rising", "CRI", "", "NM", "180", "07-06-2026 14:15:00"),
    ]
    return "\n".join(rows).encode("utf-8")


class InventoryCSVImportTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
            'WTF_CSRF_ENABLED': False,
        })
        with self.app.app_context():
            # create_app runs migrations that may create barter before init_db
            get_db().executescript('DROP TABLE IF EXISTS barter;')
            init_db()
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _post(self):
        data = {
            'type': 'inventory',
            'csv-upload': (
                io.BytesIO(_inventory_csv()),
                'inventory-test.csv',
            ),
        }
        return self.client.post(
            '/importCSV',
            data=data,
            content_type='multipart/form-data',
            base_url='https://localhost',
        )

    def test_inventory_import_separates_cards_and_sealed(self):
        resp = self._post()
        body = resp.get_json()
        print("\nRESPONSE", resp.status_code, body)

        self.assertEqual(resp.status_code, 201, body)
        self.assertEqual(body['status'], 'success')

        with self.app.app_context():
            db = get_db()

            # One auction created for the inventory import
            auctions = db.execute('SELECT * FROM auctions WHERE id != 1').fetchall()
            self.assertEqual(len(auctions), 1)
            auction = dict(auctions[0])
            self.assertEqual(auction['date_created'], '2026-06-07T09:42:30Z')

            # Cards: Pikachu x1 + Cetoddle x2 = 3 rows
            cards = db.execute(
                'SELECT card_name, card_num, condition, card_price, market_value, auction_id '
                'FROM cards ORDER BY id'
            ).fetchall()
            self.assertEqual(len(cards), 3, [dict(c) for c in cards])
            card_names = [c['card_name'] for c in cards]
            self.assertEqual(card_names.count('Pikachu'), 1)
            self.assertEqual(card_names.count('Cetoddle'), 2)

            # Sealed: ETB row
            sealed = db.execute(
                'SELECT name, quantity, price, market_value, auction_id FROM sealed'
            ).fetchall()
            self.assertEqual(len(sealed), 1, [dict(s) for s in sealed])
            self.assertEqual(sealed[0]['name'], 'Chaos Rising Pokemon Center Elite Trainer Box')
            self.assertEqual(sealed[0]['quantity'], 1)
            self.assertEqual(sealed[0]['market_value'], 180.0)

            # Auction price is the sum of per-unit buy_price rows
            # (one row per CSV line, not expanded by quantity).
            # Pikachu 4.00 * 0.8 = 3.20; Cetoddle 1.50 * 0.8 = 1.20; sealed 180.00 * 0.8 = 144.00
            expected_buy = round(4.00 * 0.8 + 1.50 * 0.8 + 180.00 * 0.8, 2)
            self.assertAlmostEqual(auction['auction_price'], expected_buy, places=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
