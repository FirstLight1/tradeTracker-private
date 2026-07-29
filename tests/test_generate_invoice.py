import tempfile
import unittest
from decimal import Decimal
from unittest.mock import patch

from flask import Flask

from tradeTracker.generateInvoice import generate_invoice, generateCreditNote


class FakePdf:
    invoices = []

    def __init__(self, invoice):
        self.invoices.append(invoice)

    def gen(self, output_path, generate_qr_code=True):
        with open(output_path, "wb") as output:
            output.write(b"%PDF-test")


class ShippingInvoiceTestCase(unittest.TestCase):
    def setUp(self):
        FakePdf.invoices.clear()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__, instance_path=self.temp_dir.name)
        self.receiver = {
            "nameAndSurname": "Test Customer",
            "address": "Test Street 1",
            "city": "Test City",
            "state": "SK",
        }
        self.shipping = {
            "shippingWay": "Doprava",
            "shippingPrice": "12.30",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("tradeTracker.generateInvoice.SimpleInvoice", FakePdf)
    def test_invoice_shipping_price_is_final_and_untaxed(self):
        with self.app.app_context():
            generate_invoice(
                self.receiver,
                "INV-1",
                shipping=self.shipping,
            )

        shipping_item = FakePdf.invoices[0]._items[-1]
        self.assertEqual(shipping_item.price, Decimal("12.30"))
        self.assertEqual(shipping_item.tax, Decimal("0"))
        self.assertEqual(shipping_item.total_tax, Decimal("12.30"))

    @patch("tradeTracker.generateInvoice.CreditNoteInvoice", FakePdf)
    def test_credit_note_shipping_price_is_final_and_untaxed(self):
        with self.app.app_context():
            generateCreditNote(
                self.receiver,
                shipping=self.shipping,
                original_invoice_num="INV-1",
            )

        shipping_item = FakePdf.invoices[0]._items[-1]
        self.assertEqual(shipping_item.price, Decimal("-12.30"))
        self.assertEqual(shipping_item.tax, Decimal("0"))
        self.assertEqual(shipping_item.total_tax, Decimal("-12.30"))


if __name__ == "__main__":
    unittest.main()
