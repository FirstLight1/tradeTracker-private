import sqlite3

import pytest

from tradeTracker.migration import createGradingTables
from tradeTracker.services.grading_service import GradingService
from tradeTracker.services.models import (
    GradeStatus,
    GradingCompleteItems,
    GradingSubmission,
    GradingSubmissionCard,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "grading-service.sqlite"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY,
            card_name TEXT NOT NULL,
            market_value REAL,
            sold_date TEXT
        );
        """
    )
    connection.close()
    createGradingTables(db_path)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        INSERT INTO cards (id, card_name, market_value, sold_date) VALUES
            (1, 'Charizard', 100, NULL),
            (2, 'Blastoise', 60, NULL),
            (3, 'Sold card', 20, '2026-07-01');
        """
    )
    yield connection
    connection.close()


def make_submission(cards=None):
    return GradingSubmission(
        grader="PSA",
        service_level="Regular",
        status=GradeStatus.PREPARING,
        submitted_at="2026-07-29",
        returned_at=None,
        notes="First batch",
        cards=cards or [
            GradingSubmissionCard(1, None, 3, 25, prep_fee=1, upcharge=0.5),
            GradingSubmissionCard(2, None, 4, 75, prep_fee=2, upcharge=1.5),
        ],
        outbound_shipping_cost=10,
        return_shipping_cost=4,
        insurance_cost=3,
        customs_duty_cost=2,
        other_shared_cost=1,
    )


def test_create_and_read_submission_allocates_costs(db):
    service = GradingService(db)

    assert service.create_submission(make_submission()) is None

    submission = service.get_submissions()[0]
    cards = service.get_submited_cards(submission["id"])
    cards_by_id = {card["card_id"]: card for card in cards}

    assert submission["status"] == GradeStatus.PREPARING
    assert submission["notes"] == "First batch"
    assert cards_by_id[1]["card_name"] == "Charizard"
    assert cards_by_id[1]["grader"] == "PSA"
    assert cards_by_id[1]["allocated_shared_cost"] == pytest.approx(5)
    assert cards_by_id[1]["total_grading_cost"] == pytest.approx(9.5)
    assert cards_by_id[2]["allocated_shared_cost"] == pytest.approx(15)
    assert cards_by_id[2]["total_grading_cost"] == pytest.approx(22.5)


@pytest.mark.parametrize("card_id", [3, 999])
def test_create_submission_rolls_back_when_card_is_unavailable(db, card_id):
    service = GradingService(db)
    submission = make_submission([
        GradingSubmissionCard(card_id, "PSA", 5, 50),
    ])

    error = service.create_submission(submission)

    assert "not available" in error
    assert db.execute("SELECT COUNT(*) FROM grading_submissions").fetchone()[0] == 0


def test_create_submission_rejects_card_in_active_submission(db):
    service = GradingService(db)
    first = make_submission([GradingSubmissionCard(1, "PSA", 5, 50)])
    second = make_submission([GradingSubmissionCard(1, "PSA", 5, 50)])
    assert service.create_submission(first) is None

    error = service.create_submission(second)

    assert "not available" in error
    assert db.execute("SELECT COUNT(*) FROM grading_submissions").fetchone()[0] == 1


def test_cancel_submission_releases_its_cards(db):
    service = GradingService(db)
    assert service.create_submission(make_submission()) is None

    assert service.cancel_submission(1) is None

    status = db.execute(
        "SELECT status FROM grading_submissions WHERE id = 1"
    ).fetchone()[0]
    current_values = db.execute(
        "SELECT is_current FROM grading_submission_cards ORDER BY card_id"
    ).fetchall()
    assert status == GradeStatus.CANCELLED
    assert [row[0] for row in current_values] == [0, 0]


def test_complete_submission_stores_grades_and_updates_market_values(db):
    service = GradingService(db)
    assert service.create_submission(make_submission()) is None
    items = [
        GradingCompleteItems(1, 9.0, "Mint", None, "CERT-1", 180),
        GradingCompleteItems(2, 8.5, "NM-MT+", "OC", "CERT-2", 95),
    ]

    assert service.complete_submission(1, items) is None

    status = db.execute(
        "SELECT status FROM grading_submissions WHERE id = 1"
    ).fetchone()[0]
    graded = db.execute(
        "SELECT card_id, grade_numeric, grade_label, qualifier, cert_number, "
        "post_grade_market_value FROM grading_submission_cards ORDER BY card_id"
    ).fetchall()
    values = db.execute("SELECT market_value FROM cards WHERE id IN (1, 2) ORDER BY id").fetchall()
    assert status == GradeStatus.GRADED
    assert tuple(graded[0]) == (1, 9.0, "Mint", None, "CERT-1", 180.0)
    assert tuple(graded[1]) == (2, 8.5, "NM-MT+", "OC", "CERT-2", 95.0)
    assert [row[0] for row in values] == [180.0, 95.0]


def test_complete_submission_rolls_back_if_card_is_not_in_submission(db):
    service = GradingService(db)
    assert service.create_submission(
        make_submission([GradingSubmissionCard(1, "PSA", 5, 50)])
    ) is None

    error = service.complete_submission(
        1, [GradingCompleteItems(2, 9, "Mint", None, "CERT-2", 95)]
    )

    assert "not in submission" in error
    assert db.execute(
        "SELECT status FROM grading_submissions WHERE id = 1"
    ).fetchone()[0] == GradeStatus.PREPARING
    assert db.execute("SELECT market_value FROM cards WHERE id = 2").fetchone()[0] == 60


def test_update_submission_status_updates_notes(db):
    service = GradingService(db)
    assert service.create_submission(
        make_submission([GradingSubmissionCard(1, "PSA", 5, 50)])
    ) is None

    assert service.update_submission_status(
        1, GradeStatus.RECEIVED_BY_GRADER, "Arrived safely"
    ) is None

    row = db.execute(
        "SELECT status, notes FROM grading_submissions WHERE id = 1"
    ).fetchone()
    assert tuple(row) == (GradeStatus.RECEIVED_BY_GRADER, "Arrived safely")
