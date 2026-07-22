"""
Unit tests for sealed FIFO inventory deduction (quantity-aware sale path).
"""
import sys
import os
import unittest
import tempfile
from datetime import date
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tradeTracker import create_app
from tradeTracker.db import get_db, init_db
from tradeTracker.services.sale_service import SaleService
from tradeTracker.services.models import SaleInput
from tradeTracker.actions import normalize


def _sale_input(sealed):
    """Minimal SaleInput carrying only sealed lines (bulk/holo/ex unused)."""
    return SaleInput(
        reciever={}, cards=[], sealed=sealed,
        bulk=None, holo=None, ex=None, shipping=None, payments=[],
    )


class SealedFIFOTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
            'WTF_CSRF_ENABLED': False,
        })
        with self.app.app_context():
            # create_app runs migrations on the (empty) temp DB which pre-creates
            # `barter`; init_db()'s schema re-creates it without a DROP, so clear it
            # first. (Same stale-harness issue affects the bulk suite.)
            get_db().executescript('DROP TABLE IF EXISTS barter;')
            init_db()
            self._setup_test_data()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _setup_test_data(self):
        db = get_db()
        # Two auctions, each holding the same product so FIFO can span rows
        db.execute('INSERT INTO auctions (id, auction_name, auction_price) VALUES (2, "A2", 50.0)')
        db.execute('INSERT INTO auctions (id, auction_name, auction_price) VALUES (3, "A3", 75.0)')
        # Product "Booster Box": 5 units in auction 2 (older), 4 units in auction 3
        db.execute(
            'INSERT INTO sealed (id, name, normalized_name, quantity, price, market_value, date, auction_id) '
            'VALUES (10, ?, ?, 5, 80.0, 100.0, "2026-01-01", 2)',
            ('Booster Box', normalize('Booster Box'))
        )
        db.execute(
            'INSERT INTO sealed (id, name, normalized_name, quantity, price, market_value, date, auction_id) '
            'VALUES (11, ?, ?, 4, 90.0, 110.0, "2026-02-01", 3)',
            ('Booster Box', normalize('Booster Box'))
        )
        # A sale row to attach sold sealed to (FK target)
        db.execute(
            'INSERT INTO sales (id, invoice_number, sale_date, total_amount) '
            'VALUES (999, "1", "2026-06-04", 0)'
        )
        db.commit()

    def _svc(self, db):
        return SaleService(db, None)

    def test_partial_sale_splits_row(self):
        """Sell 2 of a 5-unit row -> inventory row drops to 3, sold row of 2 created."""
        with self.app.app_context():
            db = get_db()
            self._svc(db)._deduct_sealed_fifo("Booster Box", 2, 999)
            db.commit()

            # Original inventory row reduced and still unsold
            row = db.execute('SELECT quantity, sale_id FROM sealed WHERE id = 10').fetchone()
            self.assertEqual(row['quantity'], 3)
            self.assertIsNone(row['sale_id'])

            # A new sold row of quantity 2 with the source row's price/auction
            sold = db.execute(
                'SELECT quantity, price, market_value, auction_id, date FROM sealed '
                'WHERE sale_id = 999'
            ).fetchall()
            self.assertEqual(len(sold), 1)
            self.assertEqual(sold[0]['quantity'], 2)
            self.assertEqual(sold[0]['price'], 80.0)
            self.assertEqual(sold[0]['market_value'], 100.0)
            self.assertEqual(sold[0]['auction_id'], 2)
            self.assertEqual(sold[0]['date'], "2026-01-01")

    def test_whole_row_sale_no_split(self):
        """Sell exactly 5 of a 5-unit row -> row stamped sold, no new row."""
        with self.app.app_context():
            db = get_db()
            self._svc(db)._deduct_sealed_fifo("Booster Box", 5, 999)
            db.commit()

            row = db.execute('SELECT quantity, sale_id FROM sealed WHERE id = 10').fetchone()
            self.assertEqual(row['quantity'], 5)
            self.assertEqual(row['sale_id'], 999)

            # No split row inserted; the only sold row is the original (id 10)
            sold = db.execute('SELECT id FROM sealed WHERE sale_id = 999').fetchall()
            self.assertEqual([r['id'] for r in sold], [10])

    def test_fifo_spans_multiple_rows(self):
        """Sell 7 -> consume all 5 from oldest row, split 2 from the next."""
        with self.app.app_context():
            db = get_db()
            self._svc(db)._deduct_sealed_fifo("Booster Box", 7, 999)
            db.commit()

            # Oldest row fully sold (whole row, quantity kept)
            r10 = db.execute('SELECT quantity, sale_id FROM sealed WHERE id = 10').fetchone()
            self.assertEqual(r10['sale_id'], 999)
            self.assertEqual(r10['quantity'], 5)

            # Second row split: 4 -> 2 remaining unsold
            r11 = db.execute('SELECT quantity, sale_id FROM sealed WHERE id = 11').fetchone()
            self.assertEqual(r11['quantity'], 2)
            self.assertIsNone(r11['sale_id'])

            # Total units sold == 7 (5 + 2)
            total_sold = db.execute(
                'SELECT COALESCE(SUM(quantity), 0) FROM sealed WHERE sale_id = 999'
            ).fetchone()[0]
            self.assertEqual(total_sold, 7)

    def test_check_inventory_guards_oversell(self):
        with self.app.app_context():
            db = get_db()
            svc = self._svc(db)
            # 9 units total available -> selling 10 must raise
            with self.assertRaises(ValueError):
                svc._check_inventory(_sale_input([{'sealedName': 'Booster Box', 'quantity': 10}]))
            # Exactly 9 is fine
            try:
                svc._check_inventory(_sale_input([{'sealedName': 'Booster Box', 'quantity': 9}]))
            except ValueError:
                self.fail("_check_inventory raised on exactly-available quantity")

    def test_open_sealed_in_auction(self):
        """/openSealed/<auction_id>: contents land in the auction, one unit marked opened."""
        import json

        client = self.app.test_client()
        resp = client.post(
            '/openSealed/2',
            data=json.dumps({
                'openedItem': {'id': 's10', 'initialValue': 100.0},
                'cards': [{
                    'cardName': 'Pikachu',
                    'cardNum': '25',
                    'condition': 'NM',
                    'marketValue': 120.0,
                    'cardmarketId': '900100',
                }],
                'sealed': [],
            }),
            content_type='application/json',
            base_url='https://localhost',
        )
        self.assertEqual(resp.status_code, 200, resp.data[:300])

        with self.app.app_context():
            db = get_db()
            # newTotal=120, initialValue=100 -> priceDiff=20 -> discounted price 100
            card = db.execute(
                'SELECT card_name, card_price, market_value, auction_id FROM cards '
                'WHERE auction_id = 2'
            ).fetchone()
            self.assertIsNotNone(card)
            self.assertEqual(card['card_name'], 'Pikachu')
            self.assertEqual(card['card_price'], 100.0)
            self.assertEqual(card['market_value'], 120.0)

            # Original row decremented 5 -> 4, still unopened
            original = db.execute('SELECT quantity, opened FROM sealed WHERE id = 10').fetchone()
            self.assertEqual(original['quantity'], 4)
            self.assertEqual(original['opened'], 0)

            # The opened unit is its own row: quantity 1 (default), opened, same auction
            opened = db.execute(
                'SELECT quantity, opened, auction_id, price FROM sealed WHERE opened = 1'
            ).fetchone()
            self.assertIsNotNone(opened)
            self.assertEqual(opened['quantity'], 1)
            self.assertEqual(opened['auction_id'], 2)
            self.assertEqual(opened['price'], 80.0)

    def test_cardmarketorder_allocates_quantity(self):
        """/cardMarketOrder emits one match with quantity=min(count, available)."""
        import json
        from tradeTracker import actions

        token = os.environ["CHROME_EXTENSION_API_TOKEN"]
        client = self.app.test_client()
        resp = client.post(
            '/cardMarketOrder',
            data=json.dumps({
                'shipping_info': {},
                'cards': [],
                'sealed': [{'name': 'Booster Box', 'count': 7}],
            }),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'},
            base_url='https://localhost',
        )
        self.assertEqual(resp.status_code, 200)
        # Result is stashed on the module global for /getLatest
        order = actions.latest
        self.assertIsNotNone(order)
        sealed = order['sealed'][0]
        self.assertEqual(sealed['quantity'], 7)   # min(7, 9 available)
        self.assertEqual(sealed['available'], 9)   # 5 + 4 across both rows
        self.assertEqual(len(sealed['id']), 1)     # one representative row id

    def test_cardmarketorder_caps_at_availability(self):
        """Requesting more than stock caps quantity at availability."""
        import json
        from tradeTracker import actions

        token = os.environ["CHROME_EXTENSION_API_TOKEN"]
        client = self.app.test_client()
        resp = client.post(
            '/cardMarketOrder',
            data=json.dumps({
                'shipping_info': {},
                'cards': [],
                'sealed': [{'name': 'Booster Box', 'count': 50}],
            }),
            content_type='application/json',
            headers={'Authorization': f'Bearer {token}'},
            base_url='https://localhost',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(actions.latest['sealed'][0]['quantity'], 9)

    def test_check_inventory_ignores_sold_rows(self):
        """Already-sold rows must not count toward availability."""
        with self.app.app_context():
            db = get_db()
            db.execute('UPDATE sealed SET sale_id = 999 WHERE id = 10')  # 5 units now sold
            db.commit()
            svc = self._svc(db)
            # Only 4 remain unsold -> 5 must raise
            with self.assertRaises(ValueError):
                svc._check_inventory(_sale_input([{'sealedName': 'Booster Box', 'quantity': 5}]))

    @unittest.skipUnless(os.environ.get("KEY"), "KEY env required for invoice encryption")
    def test_create_sale_invoice_end_to_end(self):
        """A two-unit sale from one sealed row invoices its unit price once."""
        import json

        captured_invoices = []

        class FakePdf:
            def __init__(self, invoice):
                captured_invoices.append(invoice)

            def gen(self, output_path, generate_qr_code=True):
                with open(output_path, 'wb') as output:
                    output.write(b'%PDF-test')

        client = self.app.test_client()
        with patch('tradeTracker.generateInvoice.SimpleInvoice', FakePdf):
            resp = client.post(
                '/createSale/invoice',
                data=json.dumps({
                    'paymentMethods': [{'type': 'Hotovosť', 'amount': 120}],
                    'cards': [],
                    'sealed': [{
                        'sid': 's10',
                        'auctionId': '2',
                        'sealedName': 'Booster Box',
                        'marketValue': '60',
                        'quantity': 2,
                    }],
                    'recieverInfo': {
                        'nameAndSurname': 'Test User',
                        'address': 'Test 1',
                        'city': 'Town',
                        'state': 'SK',
                        'paybackDate': date.today().isoformat(),
                        'total': 120,
                    },
                }),
                content_type='application/json',
                base_url='https://localhost',
            )
        self.assertEqual(resp.status_code, 200, resp.data[:300])
        self.assertEqual(resp.mimetype, 'application/pdf')
        sealed_item = captured_invoices[0]._items[0]
        self.assertEqual(sealed_item.count, 2)
        self.assertEqual(sealed_item.price, 60)
        self.assertEqual(sealed_item.total_tax, 120)

        with self.app.app_context():
            db = get_db()
            # Inventory row reduced to 3 and still unsold
            inv = db.execute('SELECT quantity, sale_id FROM sealed WHERE id = 10').fetchone()
            self.assertEqual(inv['quantity'], 3)
            self.assertIsNone(inv['sale_id'])
            # Exactly one sold row of quantity 2 tied to the new sale
            sold = db.execute(
                'SELECT s.quantity FROM sealed s JOIN sales sa ON s.sale_id = sa.id'
            ).fetchall()
            self.assertEqual([r['quantity'] for r in sold], [2])


if __name__ == '__main__':
    unittest.main()
