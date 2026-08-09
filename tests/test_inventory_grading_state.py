import pytest

from tradeTracker.db import get_db


@pytest.fixture
def app(tmp_path):
    from tradeTracker import create_app

    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "inventory-grading-state.sqlite"),
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db = get_db()
        db.execute("INSERT INTO auctions (id, auction_name) VALUES (2, 'Inventory')")
        db.executemany(
            "INSERT INTO cards "
            "(id, auction_id, card_name, condition, card_price, market_value) "
            "VALUES (?, 2, ?, 'NM', 10, 20)",
            [
                (10, "Raw"),
                (11, "At grader"),
                (12, "Batch graded"),
                (13, "Direct graded"),
            ],
        )
        active = db.execute(
            "INSERT INTO grading_submissions (grader, status) VALUES ('PSA', 'sent_for_grading')"
        ).lastrowid
        completed = db.execute(
            "INSERT INTO grading_submissions (grader, status) VALUES ('PSA', 'graded')"
        ).lastrowid
        db.execute(
            "INSERT INTO grading_submission_cards "
            "(submission_id, card_id, grader) VALUES (?, 11, 'PSA')",
            (active,),
        )
        db.execute(
            "INSERT INTO grading_submission_cards "
            "(submission_id, card_id, grader, grade_numeric, cert_number) "
            "VALUES (?, 12, 'PSA', 9, 'BATCH-12')",
            (completed,),
        )
        db.execute(
            "INSERT INTO grading_submission_cards "
            "(card_id, grader, grade_numeric, cert_number) "
            "VALUES (13, 'BGS', 9.5, 'DIRECT-13')"
        )
        db.commit()
    return app


def test_load_cards_distinguishes_raw_at_grader_and_graded_cards(app):
    response = app.test_client().get("/loadCards/2", base_url="https://localhost")

    assert response.status_code == 200
    cards = {card["id"]: card for card in response.get_json()}

    assert cards[10]["grading_state"] == "raw"
    assert cards[11]["grading_state"] == "at_grader"
    assert cards[11]["grading_submission_status"] == "sent_for_grading"
    assert cards[12]["grading_state"] == "graded"
    assert cards[12]["grade_numeric"] == 9
    assert cards[13]["grading_state"] == "graded"
    assert cards[13]["grading_submission_status"] is None
