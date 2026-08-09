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
            card_price REAL,
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
        INSERT INTO cards (id, card_name, card_price, market_value, sold_date) VALUES
            (1, 'Charizard', 40, 100, NULL),
            (2, 'Blastoise', 20, 60, NULL),
            (3, 'Sold card', 10, 20, '2026-07-01'),
            (4, 'Venusaur', 15, 30, NULL),
            (5, 'Pikachu', 25, 50, NULL);
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
    assert cards_by_id[1]["landed_cost"] == pytest.approx(49.5)
    assert cards_by_id[2]["allocated_shared_cost"] == pytest.approx(15)
    assert cards_by_id[2]["total_grading_cost"] == pytest.approx(22.5)
    assert cards_by_id[2]["landed_cost"] == pytest.approx(42.5)


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


def test_complete_submission_preserves_market_values_and_finalizes_costs_to_cents(db):
    service = GradingService(db)
    submission = make_submission([
        GradingSubmissionCard(1, None, 3, 2, prep_fee=1, upcharge=0.5),
        GradingSubmissionCard(2, None, 4, 1, prep_fee=2, upcharge=1.5),
    ])
    submission.outbound_shipping_cost = 10
    submission.return_shipping_cost = 0
    submission.insurance_cost = 0
    submission.customs_duty_cost = 0
    submission.other_shared_cost = 0
    assert service.create_submission(submission) is None

    assert service.complete_submission(1, [
        GradingCompleteItems(1, 9, "Mint", None, "CERT-1", None),
        GradingCompleteItems(2, 8, "NM-MT", None, "CERT-2", None),
    ]) is None

    cards = db.execute(
        "SELECT card_id, allocated_shared_cost, total_grading_cost, landed_cost "
        "FROM grading_submission_cards ORDER BY card_id"
    ).fetchall()
    market_values = db.execute(
        "SELECT market_value FROM cards WHERE id IN (1, 2) ORDER BY id"
    ).fetchall()

    assert [tuple(row) for row in cards] == [
        (1, 6.67, 11.17, 51.17),
        (2, 3.33, 10.83, 30.83),
    ]
    assert sum(row["allocated_shared_cost"] for row in cards) == pytest.approx(10.00)
    assert [row[0] for row in market_values] == [100.0, 60.0]


def test_complete_submission_distributes_small_rounding_remainder_without_negative_costs(db):
    service = GradingService(db)
    submission = make_submission([
        GradingSubmissionCard(card_id, None, 0, 1)
        for card_id in (1, 2, 4, 5)
    ])
    submission.outbound_shipping_cost = 0.02
    submission.return_shipping_cost = 0
    submission.insurance_cost = 0
    submission.customs_duty_cost = 0
    submission.other_shared_cost = 0
    assert service.create_submission(submission) is None

    assert service.complete_submission(1, [
        GradingCompleteItems(card_id, 9, "Mint", None, f"CERT-{card_id}", None)
        for card_id in (1, 2, 4, 5)
    ]) is None

    allocations = [
        row[0] for row in db.execute(
            "SELECT allocated_shared_cost FROM grading_submission_cards ORDER BY card_id"
        ).fetchall()
    ]
    assert allocations == [0.01, 0.01, 0.0, 0.0]
    assert sum(allocations) == pytest.approx(0.02)
    assert all(allocation >= 0 for allocation in allocations)


def test_complete_submission_cannot_overwrite_finalized_grade_or_costs(db):
    service = GradingService(db)
    assert service.create_submission(
        make_submission([GradingSubmissionCard(1, None, 5, 50)])
    ) is None
    assert service.complete_submission(
        1, [GradingCompleteItems(1, 9, "Mint", None, "CERT-1", 180)]
    ) is None
    finalized = db.execute(
        "SELECT grade_numeric, cert_number, total_grading_cost, landed_cost, "
        "post_grade_market_value FROM grading_submission_cards WHERE card_id = 1"
    ).fetchone()

    error = service.complete_submission(
        1, [GradingCompleteItems(1, 1, "Poor", None, "REPLACED", None)]
    )

    assert "finalized" in error
    unchanged = db.execute(
        "SELECT grade_numeric, cert_number, total_grading_cost, landed_cost, "
        "post_grade_market_value FROM grading_submission_cards WHERE card_id = 1"
    ).fetchone()
    assert tuple(unchanged) == tuple(finalized)
    assert db.execute("SELECT market_value FROM cards WHERE id = 1").fetchone()[0] == 180


def test_finalized_submission_cannot_be_moved_back_to_an_active_status(db):
    service = GradingService(db)
    assert service.create_submission(
        make_submission([GradingSubmissionCard(1, None, 5, 50)])
    ) is None
    assert service.complete_submission(
        1, [GradingCompleteItems(1, 9, "Mint", None, "CERT-1", 180)]
    ) is None

    error = service.update_submission_status(1, GradeStatus.SENT_FOR_GRADING)

    assert "finalized" in error
    assert db.execute(
        "SELECT status FROM grading_submissions WHERE id = 1"
    ).fetchone()[0] == GradeStatus.GRADED


def test_finalized_submission_cannot_be_cancelled(db):
    service = GradingService(db)
    assert service.create_submission(
        make_submission([GradingSubmissionCard(1, None, 5, 50)])
    ) is None
    assert service.complete_submission(
        1, [GradingCompleteItems(1, 9, "Mint", None, "CERT-1", 180)]
    ) is None

    error = service.cancel_submission(1)

    assert "finalized" in error
    submission = db.execute(
        "SELECT status FROM grading_submissions WHERE id = 1"
    ).fetchone()
    grading = db.execute(
        "SELECT is_current FROM grading_submission_cards WHERE card_id = 1"
    ).fetchone()
    assert submission[0] == GradeStatus.GRADED
    assert grading[0] == 1


def test_complete_submission_rolls_back_if_card_is_not_in_submission(db):
    service = GradingService(db)
    assert service.create_submission(
        make_submission([GradingSubmissionCard(1, "PSA", 5, 50)])
    ) is None

    error = service.complete_submission(
        1, [GradingCompleteItems(2, 9, "Mint", None, "CERT-2", 95)]
    )

    assert "every card" in error
    assert db.execute(
        "SELECT status FROM grading_submissions WHERE id = 1"
    ).fetchone()[0] == GradeStatus.PREPARING
    assert db.execute("SELECT market_value FROM cards WHERE id = 2").fetchone()[0] == 60


def test_complete_submission_rejects_cancelled_submission(db):
    service = GradingService(db)
    assert service.create_submission(
        make_submission([GradingSubmissionCard(1, "PSA", 5, 50)])
    ) is None
    assert service.cancel_submission(1) is None

    error = service.complete_submission(
        1, [GradingCompleteItems(1, 9, "Mint", None, "CERT-1", 180)]
    )

    assert "every card" in error
    status = db.execute(
        "SELECT status FROM grading_submissions WHERE id = 1"
    ).fetchone()[0]
    card = db.execute(
        "SELECT grade_numeric, is_current FROM grading_submission_cards WHERE card_id = 1"
    ).fetchone()
    assert status == GradeStatus.CANCELLED
    assert tuple(card) == (None, 0)


def test_complete_submission_rejects_partial_batch(db):
    service = GradingService(db)
    assert service.create_submission(make_submission()) is None

    error = service.complete_submission(
        1, [GradingCompleteItems(1, 9, "Mint", None, "CERT-1", 180)]
    )

    assert "every card" in error
    assert db.execute(
        "SELECT status FROM grading_submissions WHERE id = 1"
    ).fetchone()[0] == GradeStatus.PREPARING


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
