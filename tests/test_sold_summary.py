"""Regression coverage for sold-page payment reconciliation."""
import base64
import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tradeTracker import create_app
from tradeTracker import actions
from tradeTracker.db import get_db
from tradeTracker.services.models import ReceiptResult, SaleInput
from tradeTracker.services.sale_service import SaleService


class SoldSummaryTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
            'WTF_CSRF_ENABLED': False,
        })
        with self.app.app_context():
            db = get_db()
            db.execute('INSERT INTO auctions (id, auction_name) VALUES (2, "A2")')
            db.execute(
                'INSERT INTO cards (id, auction_id, card_name, condition, card_price, market_value) '
                'VALUES (1, 2, "Team Rocket Petrel", "NM", 9.63, 13.00)'
            )
            db.execute(
                'INSERT INTO cards (id, auction_id, card_name, condition, card_price, market_value) '
                'VALUES (2, 2, "Cynthia Roserade", "NM", 11.03, 14.89)'
            )
            db.execute(
                'INSERT INTO sealed (id, name, quantity, price, market_value, date, auction_id) '
                'VALUES (3, "Booster Box", 1, 80.00, 100.00, "2026-06-01", 2)'
            )
            db.commit()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_sold_detail_reconciles_item_subtotal_shipping_and_total(self):
        receipt_service = MagicMock()
        receipt_service.issue.return_value = ReceiptResult(kind='invoice', number='1185')
        sale_input = SaleInput(
            reciever={'total': 20.67},
            cards=[
                {'cardId': 1, 'marketValue': 8.91},
                {'cardId': 2, 'marketValue': 11.76},
            ],
            sealed=[], bulk=None, holo=None, ex=None,
            shipping={'shippingPrice': 3.50}, payments=[],
        )

        with self.app.app_context(), patch.dict(
            os.environ, {'KEY': base64.b64encode(b'0' * 16).decode()}
        ):
            sale = SaleService(get_db(), receipt_service).process_sale(sale_input)
            get_db().commit()

            # Call the view body directly so this test exercises its response contract,
            # without requiring a Cloudflare Access token.
            response = actions.loadSoldCards.__wrapped__(sale.sale_id)
            detail = response.get_json()

        self.assertEqual(detail['sale']['total_amount'], 24.17)
        self.assertEqual(detail['sale']['shipping_info'], 3.5)
        self.assertEqual(
            sum(item['invoice_sell_price'] for item in detail['cards']), 20.67
        )
        self.assertEqual(
            detail['sale']['total_amount'] - detail['sale']['shipping_info'], 20.67
        )

    def test_sealed_sale_keeps_checkout_sell_price(self):
        receipt_service = MagicMock()
        receipt_service.issue.return_value = ReceiptResult(kind='invoice', number='1186')
        sale_input = SaleInput(
            reciever={'total': 95.00}, cards=[],
            sealed=[{'sealedName': 'Booster Box', 'quantity': 1, 'marketValue': 95.00}],
            bulk=None, holo=None, ex=None, shipping=None, payments=[],
        )

        with self.app.app_context(), patch.dict(
            os.environ, {'KEY': base64.b64encode(b'0' * 16).decode()}
        ):
            sale = SaleService(get_db(), receipt_service).process_sale(sale_input)
            sold_item = dict(get_db().execute(
                'SELECT market_value, sell_price FROM sealed WHERE sale_id = ?', (sale.sale_id,)
            ).fetchone())
            get_db().commit()

        self.assertEqual(sold_item['market_value'], 100.0)
        self.assertEqual(sold_item['sell_price'], 95.0)

    def test_sales_report_uses_sealed_checkout_sell_price(self):
        receipt_service = MagicMock()
        receipt_service.issue.return_value = ReceiptResult(kind='invoice', number='1187')
        sale_input = SaleInput(
            reciever={'total': 95.00}, cards=[],
            sealed=[{'sealedName': 'Booster Box', 'quantity': 1, 'marketValue': 95.00}],
            bulk=None, holo=None, ex=None, shipping=None, payments=[],
        )

        captured = {}
        with self.app.app_context(), patch.dict(
            os.environ, {'KEY': base64.b64encode(b'0' * 16).decode()}
        ), tempfile.TemporaryDirectory() as report_dir:
            sale = SaleService(get_db(), receipt_service).process_sale(sale_input)
            get_db().execute(
                'UPDATE sales SET sale_date = "2026-06-04" WHERE id = ?', (sale.sale_id,)
            )
            get_db().commit()
            pdf_path = Path(report_dir) / 'sales.pdf'
            xls_path = Path(report_dir) / 'purchases.xlsx'
            pdf_path.touch()
            xls_path.touch()

            def capture_pdf(month, year, cards, sealed, bulk, shipping):
                captured['sealed'] = sealed
                return str(pdf_path)

            with patch.object(actions, 'generatePDF', side_effect=capture_pdf), patch.object(
                actions, 'createBuyReport', return_value=str(xls_path)
            ), self.app.test_request_context('/generateSoldReport?month=6&year=2026'):
                response = inspect.unwrap(actions.generateSoldReport)()

            response.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured['sealed'][0]['market_value'], 100.0)
        self.assertEqual(captured['sealed'][0]['sell_price'], 95.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
