import pytest

from tradeTracker.actions import orderDebit
from tradeTracker.db import get_db
from tradeTracker.services.inventory_service import InventoryService
from tradeTracker.services.models import SaleInput
from tradeTracker.services.sale_service import SaleService


@pytest.fixture
def app(tmp_path):
    from tradeTracker import create_app

    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "sealed-allocation.sqlite"),
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO auctions (id, auction_name) VALUES (2, 'First lot')")
        db.execute("INSERT INTO auctions (id, auction_name) VALUES (3, 'Second lot')")
        db.executemany(
            "INSERT INTO sealed "
            "(id, name, normalized_name, language, quantity, price, market_value, "
            "date, auction_id, cardMarketID) VALUES (?, 'Booster Box', "
            "'booster box', 'en', ?, ?, ?, ?, ?, ?)",
            [
                (10, 5, 80.0, 100.0, "2026-01-01", 2, "CM-10"),
                (11, 4, 90.0, 110.0, "2026-02-01", 3, "CM-11"),
            ],
        )
        db.execute(
            "INSERT INTO sales (id, invoice_number, sale_date, total_amount) "
            "VALUES (999, '1', '2026-09-19', 0)"
        )
        db.commit()
    return app


def test_allocate_sealed_to_sale_uses_fifo_and_splits_last_row(app):
    with app.app_context():
        db = get_db()
        InventoryService(db).allocate_sealed_to_sale(
            "booster box", "en", 7, 999, 120.0
        )

        first = db.execute(
            "SELECT quantity, sale_id, sell_price FROM sealed WHERE id = 10"
        ).fetchone()
        second = db.execute(
            "SELECT quantity, sale_id FROM sealed WHERE id = 11"
        ).fetchone()
        split = db.execute(
            "SELECT quantity, price, market_value, sell_price, date, auction_id, "
            "cardMarketID FROM sealed WHERE sale_id = 999 AND id != 10"
        ).fetchone()

        assert tuple(first) == (5, 999, 120.0)
        assert tuple(second) == (2, None)
        assert dict(split) == {
            "quantity": 2,
            "price": 90.0,
            "market_value": 110.0,
            "sell_price": 120.0,
            "date": "2026-02-01",
            "auction_id": 3,
            "cardMarketID": "CM-11",
        }
        db.rollback()


def test_sale_service_allocates_sealed_inventory_through_inventory_service(app):
    with app.app_context():
        db = get_db()
        sale_input = SaleInput(
            reciever={},
            cards=[],
            sealed=[
                {
                    "sealedName": "Booster Box",
                    "language": "en",
                    "quantity": 2,
                    "marketValue": 120,
                }
            ],
            bulk=None,
            holo=None,
            ex=None,
            shipping=None,
            payments=[],
        )

        SaleService(db, None)._insert_sale_items(999, sale_input)

        available = db.execute(
            "SELECT quantity FROM sealed WHERE id = 10"
        ).fetchone()[0]
        sold = db.execute(
            "SELECT quantity, sell_price FROM sealed WHERE sale_id = 999"
        ).fetchone()
        assert available == 3
        assert tuple(sold) == (2, 120.0)
        db.rollback()


def test_order_debit_allocates_from_the_selected_sealed_row(app):
    with app.app_context():
        db = get_db()

        error = orderDebit(
            db,
            999,
            sealed=[{"id": 11, "quantity": 3, "marketValue": 120}],
        )

        assert error is None
        available = db.execute(
            "SELECT quantity FROM sealed WHERE id = 11"
        ).fetchone()[0]
        sold = db.execute(
            "SELECT quantity, sell_price FROM sealed WHERE sale_id = 999"
        ).fetchone()
        sale_total = db.execute(
            "SELECT total_amount FROM sales WHERE id = 999"
        ).fetchone()[0]
        assert available == 1
        assert tuple(sold) == (3, 120.0)
        assert sale_total == 360.0
        db.rollback()


def test_order_debit_rejects_zero_sealed_quantity(app):
    with app.app_context():
        db = get_db()

        error = orderDebit(
            db,
            999,
            sealed=[{"id": 11, "quantity": 0, "marketValue": 120}],
        )

        assert isinstance(error, ValueError)
        row = db.execute(
            "SELECT quantity, sale_id FROM sealed WHERE id = 11"
        ).fetchone()
        assert tuple(row) == (4, None)


def test_allocate_exact_sealed_row_does_not_consume_another_lot(app):
    with app.app_context():
        db = get_db()
        service = InventoryService(db)

        with pytest.raises(ValueError, match="requested quantity"):
            service.allocate_sealed_row_to_sale(11, 5, 999, 120.0)

        rows = db.execute(
            "SELECT id, quantity, sale_id FROM sealed ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in rows] == [(10, 5, None), (11, 4, None)]


def test_fifo_rejects_insufficient_stock_before_allocating_rows(app):
    with app.app_context():
        db = get_db()
        service = InventoryService(db)

        with pytest.raises(ValueError, match="requested quantity"):
            service.allocate_sealed_to_sale("Booster Box", "en", 10, 999, 120.0)

        rows = db.execute(
            "SELECT id, quantity, sale_id FROM sealed ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in rows] == [(10, 5, None), (11, 4, None)]


def test_sealed_allocation_does_not_commit_the_callers_transaction(app):
    with app.app_context():
        db = get_db()
        InventoryService(db).allocate_sealed_row_to_sale(10, 2, 999, 120.0)

        db.rollback()

        row = db.execute(
            "SELECT quantity, sale_id FROM sealed WHERE id = 10"
        ).fetchone()
        sold_count = db.execute(
            "SELECT COUNT(*) FROM sealed WHERE sale_id = 999"
        ).fetchone()[0]
        assert tuple(row) == (5, None)
        assert sold_count == 0


@pytest.mark.parametrize("quantity", [0, -1])
def test_sealed_allocation_requires_positive_quantity(app, quantity):
    with app.app_context():
        service = InventoryService(get_db())

        with pytest.raises(ValueError, match="greater than zero"):
            service.allocate_sealed_to_sale(
                "Booster Box", "en", quantity, 999, 120.0
            )
        with pytest.raises(ValueError, match="greater than zero"):
            service.allocate_sealed_row_to_sale(10, quantity, 999, 120.0)
