import os
import tempfile
import unittest

from tradeTracker import actions, create_app
from tradeTracker.actions import normalize
from tradeTracker.db import get_db
from tradeTracker.services.models import SaleInput
from tradeTracker.services.sale_service import SaleService


def _sale_input(language, quantity):
    return SaleInput(
        reciever={},
        cards=[],
        sealed=[
            {
                "sealedName": "Booster Box",
                "language": language,
                "quantity": quantity,
            }
        ],
        bulk=None,
        holo=None,
        ex=None,
        shipping=None,
        payments=[],
    )


class SealedLanguageTestCase(unittest.TestCase):
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
            db = get_db()
            db.execute(
                "INSERT INTO auctions (id, auction_name, auction_price) "
                'VALUES (2, "Languages", 100.0)'
            )
            rows = [
                (10, "en", 5, 2),
                (11, "jp", 3, 2),
                (12, "en", 2, None),
            ]
            for sealed_id, language, quantity, auction_id in rows:
                db.execute(
                    "INSERT INTO sealed "
                    "(id, name, normalized_name, language, quantity, price, "
                    "market_value, date, auction_id) "
                    'VALUES (?, ?, ?, ?, ?, 80.0, 100.0, "2026-01-01", ?)',
                    (
                        sealed_id,
                        "Booster Box",
                        normalize("Booster Box"),
                        language,
                        quantity,
                        auction_id,
                    ),
                )
            db.execute(
                "INSERT INTO sales (id, invoice_number, sale_date, total_amount) "
                'VALUES (999, "1", "2026-06-04", 0)'
            )
            db.execute(
                "INSERT INTO sealed "
                "(id, name, normalized_name, language, quantity, price, "
                "market_value, date, auction_id, opened) "
                'VALUES (13, ?, ?, "jp", 4, 80.0, 100.0, '
                '"2026-01-01", 2, 1)',
                ("Booster Box", normalize("Booster Box")),
            )
            db.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_inventory_check_is_language_specific(self):
        with self.app.app_context():
            service = SaleService(get_db(), None)
            service._check_inventory(_sale_input("jp", 3))
            with self.assertRaises(ValueError):
                service._check_inventory(_sale_input("jp", 4))
            with self.assertRaises(ValueError):
                service._check_inventory(_sale_input("de", 1))
            with self.assertRaises(ValueError):
                service._check_inventory(_sale_input("jp", 0))

    def test_fifo_preserves_language_and_does_not_touch_other_stock(self):
        with self.app.app_context():
            db = get_db()
            SaleService(db, None)._deduct_sealed_fifo("Booster Box", "jp", 2, 999, 120.0)
            db.commit()

            english = db.execute("SELECT quantity, sale_id FROM sealed WHERE id = 10").fetchone()
            japanese = db.execute("SELECT quantity, sale_id FROM sealed WHERE id = 11").fetchone()
            sold = db.execute(
                "SELECT language, quantity, sell_price FROM sealed WHERE sale_id = 999"
            ).fetchone()

            self.assertEqual((english["quantity"], english["sale_id"]), (5, None))
            self.assertEqual((japanese["quantity"], japanese["sale_id"]), (1, None))
            self.assertEqual(
                dict(sold),
                {
                    "language": "jp",
                    "quantity": 2,
                    "sell_price": 120.0,
                },
            )

    def test_search_groups_same_product_by_language(self):
        response = self.client.post(
            "/searchCard",
            json={"query": "Booster Box", "cartIds": []},
            base_url="https://localhost",
        )
        self.assertEqual(response.status_code, 200, response.data)
        sealed = [item for item in response.get_json()["value"] if "sid" in item]
        counts = {item["language"]: item["available_count"] for item in sealed}
        self.assertEqual(counts, {"en": 7, "jp": 3})

    def test_load_endpoints_return_language(self):
        standalone = self.client.get("/loadSealed", base_url="https://localhost")
        auction = self.client.get("/loadSealed/2", base_url="https://localhost")

        self.assertEqual(standalone.status_code, 200, standalone.data)
        self.assertEqual(standalone.get_json()["data"][0]["language"], "en")
        self.assertEqual(auction.status_code, 200, auction.data)
        self.assertEqual(
            {item["language"] for item in auction.get_json()},
            {"en", "jp"},
        )

    def test_load_sale_returns_sealed_language(self):
        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE sealed SET sale_id = 999 WHERE id = 11")
            db.commit()

        response = self.client.get("/loadSale/999", base_url="https://localhost")
        self.assertEqual(response.status_code, 200, response.data)
        items = response.get_json()["data"]["items"]
        self.assertEqual(items[0]["language"], "jp")

    def test_update_sealed_validates_and_persists_language(self):
        response = self.client.patch(
            "/updateSealed/s10",
            json={"field": "language", "value": "de"},
            base_url="https://localhost",
        )
        self.assertEqual(response.status_code, 200, response.data)

        invalid = self.client.patch(
            "/updateSealed/s10",
            json={"field": "language", "value": "xx"},
            base_url="https://localhost",
        )
        self.assertEqual(invalid.status_code, 400, invalid.data)

        invalid_id = self.client.patch(
            "/updateSealed/²",
            json={"field": "language", "value": "en"},
            base_url="https://localhost",
        )
        self.assertEqual(invalid_id.status_code, 400, invalid_id.data)

        with self.app.app_context():
            language = (
                get_db().execute("SELECT language FROM sealed WHERE id = 10").fetchone()["language"]
            )
            self.assertEqual(language, "de")

    def test_cardmarket_order_matches_requested_language(self):
        response = self.client.post(
            "/cardMarketOrder",
            json={
                "shipping_info": {},
                "cards": [],
                "sealed": [
                    {
                        "name": "Booster Box",
                        "language": "jp",
                        "count": 5,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {os.environ['CHROME_EXTENSION_API_TOKEN']}"},
            base_url="https://localhost",
        )
        self.assertEqual(response.status_code, 200, response.data)
        matched = actions.latest["sealed"][0]
        self.assertEqual(matched["language"], "jp")
        self.assertEqual(matched["quantity"], 3)
        self.assertEqual(matched["available"], 3)

    def test_cardmarket_order_rejects_non_positive_count(self):
        response = self.client.post(
            "/cardMarketOrder",
            json={
                "shipping_info": {},
                "cards": [],
                "sealed": [
                    {
                        "name": "Booster Box",
                        "language": "jp",
                        "count": -1,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {os.environ['CHROME_EXTENSION_API_TOKEN']}"},
            base_url="https://localhost",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_cardmarket_import_rejects_invalid_count(self):
        response = self.client.post(
            "/CardMarketTable",
            json={
                "cards": [],
                "sealed": [
                    {
                        "name": "Booster Box",
                        "language": "jp",
                        "count": -1,
                        "marketValue": 100,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {os.environ['CHROME_EXTENSION_API_TOKEN']}"},
            base_url="https://localhost",
        )
        self.assertEqual(response.status_code, 400, response.data)

        with self.app.app_context():
            count = get_db().execute("SELECT COUNT(*) FROM sealed WHERE id > 13").fetchone()[0]
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
