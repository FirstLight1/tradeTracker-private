import base64
from unittest.mock import MagicMock, patch

import pytest

from tradeTracker.db import get_db
from tradeTracker.services.models import ReceiptResult, SaleInput
from tradeTracker.services.sale_service import SaleService


@pytest.fixture
def app(tmp_path):
    from tradeTracker import create_app

    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "graded-sale.sqlite"),
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO auctions (id, auction_name) VALUES (2, 'Graded')")
        db.execute(
            "INSERT INTO cards "
            "(id, auction_id, card_name, card_num, condition, card_price, market_value) "
            "VALUES (10, 2, 'Charizard', '4/102', 'NM', 100, 500)"
        )
        db.commit()
    return app


def sale_input():
    return SaleInput(
        reciever={"total": 450},
        cards=[{
            "cardId": 10,
            "cardName": "untrusted name",
            "cardNum": "untrusted number",
            "marketValue": 450,
        }],
        sealed=[], bulk=None, holo=None, ex=None, shipping=None, payments=[],
    )


def add_grading(db, status):
    cursor = db.execute(
        "INSERT INTO grading_submissions (grader, status) VALUES ('PSA', ?)",
        (status,),
    )
    db.execute(
        "INSERT INTO grading_submission_cards "
        "(submission_id, card_id, grader, total_grading_cost, landed_cost, "
        "grade_numeric, grade_label, cert_number, post_grade_market_value) "
        "VALUES (?, 10, 'PSA', 25, 125, 10, 'Gem Mint', 'CERT-10', 500)",
        (cursor.lastrowid,),
    )
    db.commit()


def test_card_at_grader_cannot_be_sold(app):
    receipt_service = MagicMock()
    with app.app_context():
        add_grading(get_db(), "sent_for_grading")

        with pytest.raises(ValueError, match="not available"):
            SaleService(get_db(), receipt_service).process_sale(sale_input())

        assert get_db().execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0
        receipt_service.issue.assert_not_called()


def test_completed_graded_card_sale_snapshots_costs_and_invoice_identity(app):
    receipt_service = MagicMock()
    receipt_service.issue.return_value = ReceiptResult(kind="invoice", number="1")
    with app.app_context(), patch.dict(
        "os.environ", {"KEY": base64.b64encode(b"0" * 16).decode()}
    ):
        add_grading(get_db(), "graded")

        result = SaleService(get_db(), receipt_service).process_sale(sale_input())
        sold = get_db().execute(
            "SELECT sell_price, profit, internal_cost, internal_profit "
            "FROM sale_items WHERE sale_id = ?", (result.sale_id,)
        ).fetchone()
        get_db().commit()

    issued_card = receipt_service.issue.call_args.args[0].cards[0]
    assert issued_card["cardName"] == "Charizard"
    assert issued_card["cardNum"] == "4/102"
    assert issued_card["displayCondition"] == "PSA 10 Gem Mint"
    assert issued_card["certNumber"] == "CERT-10"
    assert tuple(sold) == pytest.approx((450, 350, 125, 325))
