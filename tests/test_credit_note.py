"""
Tests for credit note creation pipeline — transaction atomicity and
record_number uniqueness.

These tests verify the two correctness fixes:
  1. PDF generation failure rolls back the entire transaction (return +
     correction), so a retry won't double-return.
  2. sales_correction.record_number is unique per change_type (UNIQUE index).
  3. Happy path: correction row created, return applied, PDF returned.
"""
import sys
import os
import unittest
import tempfile
import json
import sqlite3
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tradeTracker import create_app
from tradeTracker.db import get_db, init_db


class CreditNoteTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
            'WTF_CSRF_ENABLED': False,
        })
        with self.app.app_context():
            init_db()
            self._setup_test_data()
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _setup_test_data(self):
        db = get_db()
        db.execute(
            'INSERT INTO sales (id, invoice_number, sale_date, total_amount, shipping_info) '
            'VALUES (500, "INV-100", "2026-07-01", 150.0, 10.0)'
        )
        db.execute(
            'INSERT INTO cards (id, auction_id, card_name, card_num, condition, card_price, market_value, sold_date) '
            'VALUES (1000, 1, "Lightning Bolt", "LB-001", "NM", 5.0, 20.0, "2026-07-01")'
        )
        db.execute(
            'INSERT INTO sale_items (id, sale_id, card_id, sell_price, profit) '
            'VALUES (1, 500, 1000, 50.0, 45.0)'
        )
        db.commit()

    def _payload(self, **overrides):
        payload = {
            'items': [{
                'id': 1000,
                'card_name': 'Lightning Bolt',
                'card_num': 'LB-001',
                'condition': 'NM',
                'sell_price': 50.0,
            }],
            'sealed': [],
            'bulk': None,
            'holo': None,
            'ex': None,
            'shipping': {
                'shippingWay': 'Doprava',
                'shippingPrice': 10.0,
            },
            'reciever': {
                'nameAndSurname': 'Test Customer',
                'address': 'Test Street 1',
                'city': 'Test City',
                'state': 'SK',
                'paybackDate': date.today().isoformat(),
                'paymentMethod': 'Bankovy prevod',
            },
            'originalInvoiceNum': 'INV-100',
        }
        payload.update(overrides)
        return payload

    # --- Test (a): PDF gen failure → full rollback ---

    @patch('tradeTracker.generateInvoice.generateCreditNote', side_effect=Exception("PDF boom"))
    def test_pdf_failure_rolls_back_transaction(self, _mock):
        """When PDF generation fails, no sales_correction row and no inventory mutation."""
        with self.app.app_context():
            db = get_db()
            si_before = db.execute('SELECT COUNT(*) FROM sale_items WHERE sale_id = 500').fetchone()[0]
            self.assertEqual(si_before, 1)

        resp = self.client.post(
            '/generateCreditNote/500',
            data=json.dumps(self._payload()),
            content_type='application/json',
            base_url='https://localhost',
        )

        self.assertEqual(resp.status_code, 500)
        data = resp.get_json()
        self.assertIn('Ax06', data['message'])

        with self.app.app_context():
            db = get_db()
            corrections = db.execute('SELECT COUNT(*) FROM sales_correction').fetchone()[0]
            self.assertEqual(corrections, 0, "sales_correction row should not exist after PDF failure")

            si_after = db.execute('SELECT COUNT(*) FROM sale_items WHERE sale_id = 500').fetchone()[0]
            self.assertEqual(si_after, 1, "sale_items should not be deleted after rollback")

            card = db.execute('SELECT sold_date FROM cards WHERE id = 1000').fetchone()
            self.assertIsNotNone(card['sold_date'], "sold_date should not be nulled after rollback")

            sale = db.execute('SELECT total_amount FROM sales WHERE id = 500').fetchone()
            self.assertEqual(sale['total_amount'], 150.0, "total_amount should not be decremented after rollback")

    # --- Test (b): record_number uniqueness ---

    def test_record_number_unique_per_change_type(self):
        """Duplicate (record_number, change_type) pair must raise IntegrityError."""
        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO sales_correction (sale_id, record_number, change_type, value_change) "
                "VALUES (500, 1, 'credit', 50.0)"
            )
            db.commit()

            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(
                        "INSERT INTO sales_correction (sale_id, record_number, change_type, value_change) "
                        "VALUES (500, 1, 'credit', 30.0)"
                    )
                    db.commit()
            finally:
                db.rollback()

    def test_record_number_unique_index_exists(self):
        """The UNIQUE index must be present in the schema."""
        with self.app.app_context():
            db = get_db()
            idx = db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_sales_correction_record_unique'"
            ).fetchone()
            self.assertIsNotNone(idx, "UNIQUE index idx_sales_correction_record_unique must exist")

    # --- Test (c): happy path ---

    @patch('tradeTracker.generateInvoice.generateCreditNote')
    def test_happy_path_commits_correction_and_returns_pdf(self, mock_gen):
        """Successful credit note: correction row created, return applied, PDF returned."""
        mock_gen.return_value = (
            {'bytes': b'%PDF-1.4 fake', 'filename': 'Dobropis_test.pdf', 'path': '/tmp/test.pdf'},
            1,
        )

        resp = self.client.post(
            '/generateCreditNote/500',
            data=json.dumps(self._payload()),
            content_type='application/json',
            base_url='https://localhost',
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, 'application/pdf')
        self.assertEqual(resp.headers['Content-Disposition'], 'attachment; filename=Dobropis_test.pdf')

        with self.app.app_context():
            db = get_db()

            corrections = db.execute(
                'SELECT sale_id, record_number, change_type, value_change FROM sales_correction'
            ).fetchall()
            self.assertEqual(len(corrections), 1)
            self.assertEqual(corrections[0]['sale_id'], 500)
            self.assertEqual(corrections[0]['record_number'], 1)
            self.assertEqual(corrections[0]['change_type'], 'credit')
            self.assertAlmostEqual(corrections[0]['value_change'], 60.0, places=2)

            si_after = db.execute('SELECT COUNT(*) FROM sale_items WHERE sale_id = 500').fetchone()[0]
            self.assertEqual(si_after, 0, "sale_items should be deleted on successful return")

            card = db.execute('SELECT sold_date FROM cards WHERE id = 1000').fetchone()
            self.assertIsNone(card['sold_date'], "sold_date should be nulled on successful return")

            sale = db.execute('SELECT total_amount FROM sales WHERE id = 500').fetchone()
            self.assertIsNotNone(sale, "sale row should survive (audit trail for sales_correction)")
            self.assertAlmostEqual(sale['total_amount'], 90.0, places=2,
                                   msg="total_amount should be decremented by returned_value (150 - 60)")

    @patch('tradeTracker.generateInvoice.generateCreditNote')
    def test_happy_path_increments_record_number(self, mock_gen):
        """Second credit note gets record_number = 2."""
        mock_gen.return_value = (
            {'bytes': b'%PDF-1.4 fake', 'filename': 'Dobropis_test2.pdf', 'path': '/tmp/test2.pdf'},
            2,
        )

        with self.app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO sales_correction (sale_id, record_number, change_type, value_change) "
                "VALUES (500, 1, 'credit', 30.0)"
            )
            db.commit()

        resp = self.client.post(
            '/generateCreditNote/500',
            data=json.dumps(self._payload()),
            content_type='application/json',
            base_url='https://localhost',
        )

        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            db = get_db()
            rn = db.execute(
                "SELECT record_number FROM sales_correction ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(rn['record_number'], 2)

    # --- Test (d): _orderReturn failure does not leave partial state ---

    def test_order_return_failure_rolls_back(self):
        """If _orderReturn fails (e.g. sealed exceeds available), no correction row."""
        payload = self._payload(sealed=[{'id': 9999, 'returnQuantity': 5, 'market_value': 100.0}])

        resp = self.client.post(
            '/generateCreditNote/500',
            data=json.dumps(payload),
            content_type='application/json',
            base_url='https://localhost',
        )

        self.assertIn(resp.status_code, (400, 500))

        with self.app.app_context():
            db = get_db()
            corrections = db.execute('SELECT COUNT(*) FROM sales_correction').fetchone()[0]
            self.assertEqual(corrections, 0, "No correction row when _orderReturn fails")

            si_after = db.execute('SELECT COUNT(*) FROM sale_items WHERE sale_id = 500').fetchone()[0]
            self.assertEqual(si_after, 1, "sale_items should not be deleted when _orderReturn fails")


if __name__ == '__main__':
    unittest.main()
