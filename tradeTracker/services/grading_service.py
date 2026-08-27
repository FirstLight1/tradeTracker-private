import tradeTracker.services.models as models
from datetime import date
from decimal import Decimal
from typing import Any

from tradeTracker.services.grading_validation import (
    ValidationError,
    allocate_largest_remainder,
    grade_number,
    money,
    normalize_date,
    normalize_text,
    rounded_money,
    validate_chronology,
)


ACTIVE_STATUSES = {
    models.GradeStatus.PREPARING,
    models.GradeStatus.SENT_FOR_GRADING,
    models.GradeStatus.RECEIVED_BY_GRADER,
}
TERMINAL_STATUSES = {
    models.GradeStatus.GRADED,
    models.GradeStatus.RETURNED,
    models.GradeStatus.CANCELLED,
}
SHARED_COST_FIELDS = (
    "outbound_shipping_cost",
    "return_shipping_cost",
    "insurance_cost",
    "customs_duty_cost",
    "other_shared_cost",
)


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _db_number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


class GradingService:
    def __init__(self, db):
        self.db = db
        self.validation_errors: dict[str, str] = {}

    def _capture_error(self, error: Exception, prefix: str) -> str:
        self.validation_errors = error.errors if isinstance(error, ValidationError) else {}
        return prefix + str(error)

    # TODO: add pagination
    def get_submissions(self) -> list[dict[str, Any]]:
        submissions = self.db.execute(
            "SELECT * FROM grading_submissions ORDER BY id DESC"
        ).fetchall()
        return [dict(submission) for submission in submissions]

    def get_submission(self, submission_id: int) -> dict[str, Any] | None:
        submission = self.db.execute(
            "SELECT * FROM grading_submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        return dict(submission) if submission else None

    def get_submited_cards(self, submission_id: int) -> list[dict[str, Any]]:
        cards = self.db.execute(
            "SELECT * FROM grading_submission_cards gd JOIN cards c "
            "ON gd.card_id = c.id "
            "WHERE gd.submission_id = ?",
            (submission_id,),
        ).fetchall()
        return [dict(card) for card in cards]

    def _submission_allocations(self, submission, rows) -> list[Decimal]:
        shared_total = rounded_money(
            sum((_decimal(submission[field]) for field in SHARED_COST_FIELDS), Decimal("0"))
        )
        return allocate_largest_remainder(
            shared_total, (_decimal(row["submitted_value"]) for row in rows)
        )

    def _normalized_result(self, item: models.GradingCompleteItems) -> dict[str, Any]:
        return {
            "card_id": int(item.card_id),
            "grader": normalize_text(item.grader, "grader"),
            "grade_numeric": grade_number(item.grade_numeric),
            "grade_label": normalize_text(item.grade_label, "grade_label"),
            "qualifier": normalize_text(item.qualifier, "qualifier"),
            "cert_number": normalize_text(item.cert_number, "cert_number"),
            "post_grade_market_value": money(
                item.post_grade_market_value, "post_grade_market_value", nullable=True
            ),
        }

    @staticmethod
    def _result_matches(row, result: dict[str, Any]) -> bool:
        stored = {
            "grader": normalize_text(row["grader"], "grader"),
            "grade_numeric": (
                Decimal(str(row["grade_numeric"])) if row["grade_numeric"] is not None else None
            ),
            "grade_label": normalize_text(row["grade_label"], "grade_label"),
            "qualifier": normalize_text(row["qualifier"], "qualifier"),
            "cert_number": normalize_text(row["cert_number"], "cert_number"),
            "post_grade_market_value": (
                Decimal(str(row["post_grade_market_value"]))
                if row["post_grade_market_value"] is not None
                else None
            ),
        }
        incoming = {key: result[key] for key in stored}
        return stored == incoming

    def create_submission(self, submission: models.GradingSubmission) -> str | None:
        self.validation_errors = {}
        try:
            self.db.execute("BEGIN IMMEDIATE")
            if not submission.cards:
                raise ValidationError("A submission must contain at least one card")
            status = models.GradeStatus(submission.status)
            if status not in ACTIVE_STATUSES:
                raise ValidationError("A new submission must have an active status")

            grader = normalize_text(submission.grader, "grader", required=True)
            service_level = normalize_text(submission.service_level, "service_level")
            notes = normalize_text(submission.notes, "notes")
            submitted_at = normalize_date(submission.submitted_at, "submitted_at", required=True)
            if submission.returned_at is not None:
                raise ValidationError("An active submission cannot have returned_at")
            shared_costs = {
                field: money(getattr(submission, field), field) for field in SHARED_COST_FIELDS
            }

            normalized_cards = []
            seen_ids = set()
            card_prices = {}
            for card in submission.cards:
                card_id = int(card.card_id)
                if card_id in seen_ids:
                    raise ValidationError(f"Card with id:{card_id} appears more than once")
                seen_ids.add(card_id)
                normalized_cards.append(
                    {
                        "card_id": card_id,
                        "grader": normalize_text(card.grader, "card grader") or grader,
                        "grading_fee": money(card.grading_fee, "grading_fee"),
                        "prep_fee": money(card.prep_fee, "prep_fee"),
                        "upcharge": money(card.upcharge, "upcharge"),
                        "submitted_value": money(card.submitted_value, "submitted_value"),
                    }
                )

                available = self.db.execute(
                    "SELECT c.id, c.card_price FROM cards c WHERE c.id = ? "
                    "AND c.sold_date IS NULL "
                    "AND NOT EXISTS (SELECT 1 FROM sale_items si WHERE si.card_id = c.id) "
                    "AND NOT EXISTS ("
                    "SELECT 1 FROM grading_submission_cards gsc "
                    "WHERE gsc.card_id = c.id AND gsc.is_current = 1)",
                    (card_id,),
                ).fetchone()

                if not available:
                    raise ValidationError(f"Card with id:{card_id} is not available")
                card_prices[card_id] = available["card_price"]

            allocations = allocate_largest_remainder(
                rounded_money(sum(shared_costs.values(), Decimal("0"))),
                (card["submitted_value"] for card in normalized_cards),
            )
            cursor = self.db.execute(
                "INSERT INTO grading_submissions "
                "(grader, service_level, status, outbound_shipping_cost, return_shipping_cost, "
                "insurance_cost, customs_duty_cost, other_shared_cost, submitted_at, returned_at, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                (
                    grader,
                    service_level,
                    status.value,
                    *(_db_number(shared_costs[field]) for field in SHARED_COST_FIELDS),
                    submitted_at,
                    notes,
                ),
            )
            submission_id = cursor.lastrowid
            for card, allocated in zip(normalized_cards, allocations):
                direct = card["grading_fee"] + card["prep_fee"] + card["upcharge"]
                total = rounded_money(direct + allocated)
                card_price = card_prices[card["card_id"]]
                landed = (
                    rounded_money(_decimal(card_price) + total) if card_price is not None else None
                )
                self.db.execute(
                    "INSERT INTO grading_submission_cards "
                    "(submission_id, card_id, grader, grading_fee, prep_fee, submitted_value, "
                    "allocated_shared_cost, upcharge_fee, total_grading_cost, landed_cost, cert_number) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                    (
                        submission_id,
                        card["card_id"],
                        card["grader"],
                        _db_number(card["grading_fee"]),
                        _db_number(card["prep_fee"]),
                        _db_number(card["submitted_value"]),
                        _db_number(allocated),
                        _db_number(card["upcharge"]),
                        _db_number(total),
                        _db_number(landed),
                    ),
                )
            self.db.commit()
            return None
        except Exception as error:
            self.db.rollback()
            return self._capture_error(error, "Failed to create submission | ")

    def cancel_submission(self, submission_id: int) -> str | None:
        self.validation_errors = {}
        try:
            self.db.execute("BEGIN IMMEDIATE")
            current = self.db.execute(
                "SELECT status FROM grading_submissions WHERE id = ?", (submission_id,)
            ).fetchone()
            if not current:
                raise ValidationError(f"Submission with id:{submission_id} was not found")
            if models.GradeStatus(current["status"]) in TERMINAL_STATUSES:
                raise ValidationError("Submission is already finalized")
            self.db.execute(
                "UPDATE grading_submissions SET status = ? WHERE id = ?",
                (models.GradeStatus.CANCELLED.value, submission_id),
            )
            self.db.execute(
                "UPDATE grading_submission_cards SET is_current = 0 WHERE submission_id = ?",
                (submission_id,),
            )
            self.db.commit()
            return None
        except Exception as error:
            self.db.rollback()
            return self._capture_error(error, "Failed to cancel submission | ")

    def complete_submission(
        self,
        submission_id: int,
        items: list[models.GradingCompleteItems],
        returned_at: str | None = None,
    ) -> str | None:
        self.validation_errors = {}
        try:
            self.db.execute("BEGIN IMMEDIATE")
            submission = self.db.execute(
                "SELECT * FROM grading_submissions WHERE id = ?", (submission_id,)
            ).fetchone()
            if not submission:
                raise ValidationError(f"Submission with id:{submission_id} was not found")

            status = models.GradeStatus(submission["status"])
            if status in {models.GradeStatus.RETURNED, models.GradeStatus.CANCELLED}:
                raise ValidationError("Completion is only allowed from an active submission")

            rows = self.db.execute(
                "SELECT gsc.*, c.card_price FROM grading_submission_cards gsc "
                "JOIN cards c ON c.id = gsc.card_id "
                "WHERE gsc.submission_id = ? AND gsc.is_current = 1 ORDER BY gsc.card_id",
                (submission_id,),
            ).fetchall()

            results = [self._normalized_result(item) for item in items]
            if len({result["card_id"] for result in results}) != len(results):
                raise ValidationError("Completion cannot contain duplicate cards")
            expected_ids = {row["card_id"] for row in rows}
            if not expected_ids or {result["card_id"] for result in results} != expected_ids:
                raise ValidationError("Completion must include every card in the submission")

            rows_by_id = {row["card_id"]: row for row in rows}
            for result in results:
                result["grader"] = result["grader"] or normalize_text(
                    rows_by_id[result["card_id"]]["grader"], "grader", required=True
                )
                if result["grade_numeric"] is None and result["grade_label"] is None:
                    raise ValidationError(
                        {
                            f"cards.{result['card_id']}.grade_numeric": (
                                "Enter a numeric grade or grade label, or mark the submission returned ungraded"
                            )
                        }
                    )
            if status == models.GradeStatus.GRADED:
                if all(
                    self._result_matches(rows_by_id[result["card_id"]], result)
                    for result in results
                ):
                    self.db.commit()
                    return None
                raise ValidationError("Submission is already finalized with different results")
            if status not in ACTIVE_STATUSES:
                raise ValidationError("Completion is only allowed from an active submission")

            certificates = [
                (result["card_id"], result["grader"], result["cert_number"])
                for result in results
                if result["cert_number"]
            ]
            canonical_certificates = [
                (grader.casefold(), certificate.casefold())
                for _, grader, certificate in certificates
            ]
            if len(canonical_certificates) != len(set(canonical_certificates)):
                raise ValidationError(
                    {"cert_number": "Certificate numbers must be unique for each grader"}
                )
            for card_id, grader, certificate in certificates:
                duplicate = self.db.execute(
                    "SELECT 1 FROM grading_submission_cards "
                    "WHERE card_id != ? AND cert_number IS NOT NULL "
                    "AND LOWER(TRIM(grader)) = LOWER(TRIM(?)) "
                    "AND LOWER(TRIM(cert_number)) = LOWER(TRIM(?))",
                    (card_id, grader, certificate),
                ).fetchone()
                if duplicate:
                    raise ValidationError(
                        {
                            f"cards.{card_id}.cert_number": "Certificate is already assigned to another card"
                        }
                    )

            completed_at = normalize_date(
                returned_at if returned_at is not None else date.today(),
                "returned_at",
                required=True,
            )
            submitted_at = normalize_date(submission["submitted_at"], "submitted_at", required=True)
            validate_chronology(submitted_at, completed_at)
            allocations = self._submission_allocations(submission, rows)
            for row, allocated in zip(rows, allocations):
                direct = sum(
                    (_decimal(row[field]) for field in ("grading_fee", "prep_fee", "upcharge_fee")),
                    Decimal("0"),
                )
                total = rounded_money(direct + allocated)
                landed = (
                    rounded_money(_decimal(row["card_price"]) + total)
                    if row["card_price"] is not None
                    else None
                )
                result = next(item for item in results if item["card_id"] == row["card_id"])
                self.db.execute(
                    "UPDATE grading_submission_cards SET grader = ?, grade_numeric = ?, "
                    "grade_label = ?, qualifier = ?, cert_number = ?, post_grade_market_value = ?, "
                    "allocated_shared_cost = ?, total_grading_cost = ?, landed_cost = ? "
                    "WHERE id = ? AND is_current = 1",
                    (
                        result["grader"],
                        _db_number(result["grade_numeric"]),
                        result["grade_label"],
                        result["qualifier"],
                        result["cert_number"],
                        _db_number(result["post_grade_market_value"]),
                        _db_number(allocated),
                        _db_number(total),
                        _db_number(landed),
                        row["id"],
                    ),
                )
                if result["post_grade_market_value"] is not None:
                    self.db.execute(
                        "UPDATE cards SET market_value = ? WHERE id = ?",
                        (_db_number(result["post_grade_market_value"]), row["card_id"]),
                    )
            self.db.execute(
                "UPDATE grading_submissions SET status = ?, returned_at = ? WHERE id = ?",
                (models.GradeStatus.GRADED.value, completed_at, submission_id),
            )
            self.db.commit()
            return None
        except Exception as error:
            self.db.rollback()
            return self._capture_error(error, "Failed to complete submission | ")

    def update_submission_status(
        self,
        submission_id: int,
        status: models.GradeStatus,
        notes: str | None = None,
        returned_at: str | None = None,
    ) -> str | None:
        self.validation_errors = {}
        try:
            self.db.execute("BEGIN IMMEDIATE")
            target = models.GradeStatus(status)
            if target == models.GradeStatus.GRADED:
                raise ValidationError("Use complete_submission to mark a submission graded")
            if target not in ACTIVE_STATUSES | {
                models.GradeStatus.RETURNED,
                models.GradeStatus.CANCELLED,
            }:
                raise ValidationError("Invalid submission status")
            current = self.db.execute(
                "SELECT status, submitted_at FROM grading_submissions WHERE id = ?",
                (submission_id,),
            ).fetchone()
            if not current:
                raise ValidationError(f"Submission with id:{submission_id} was not found")
            if models.GradeStatus(current["status"]) in TERMINAL_STATUSES:
                raise ValidationError("Submission is already finalized")

            normalized_notes = normalize_text(notes, "notes")
            normalized_returned_at = None
            if target == models.GradeStatus.RETURNED:
                if not normalized_notes:
                    raise ValidationError({"notes": "Explain why the submission was returned"})
                normalized_returned_at = normalize_date(
                    returned_at if returned_at is not None else date.today(),
                    "returned_at",
                    required=True,
                )
                submitted_at = normalize_date(
                    current["submitted_at"], "submitted_at", required=True
                )
                validate_chronology(submitted_at, normalized_returned_at)
            self.db.execute(
                "UPDATE grading_submissions SET status = ?, notes = ?, returned_at = ? WHERE id = ?",
                (target.value, normalized_notes, normalized_returned_at, submission_id),
            )
            if target in {models.GradeStatus.RETURNED, models.GradeStatus.CANCELLED}:
                self.db.execute(
                    "UPDATE grading_submission_cards SET is_current = 0 WHERE submission_id = ?",
                    (submission_id,),
                )
            self.db.commit()
            return None
        except Exception as error:
            self.db.rollback()
            return self._capture_error(error, "Failed to update submission | ")

    def grade_card(self, card_id: int, grade: models.GradingCompleteItems) -> str | None:
        self.validation_errors = {}
        try:
            self.db.execute("BEGIN IMMEDIATE")
            result = self._normalized_result(grade)
            if result["card_id"] != int(card_id):
                raise ValidationError("card_id does not match grading result")
            if not result["grader"]:
                raise ValidationError("grader is required")
            if result["grade_numeric"] is None and result["grade_label"] is None:
                raise ValidationError("A numeric grade or grade label is required")

            available = self.db.execute(
                "SELECT c.id FROM cards c WHERE c.id = ? AND c.sold_date IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM grading_submission_cards gsc "
                "WHERE gsc.card_id = c.id AND gsc.is_current = 1) "
                "AND NOT EXISTS (SELECT 1 FROM sale_items si WHERE si.card_id = c.id)",
                (card_id,),
            ).fetchone()
            if not available:
                raise ValidationError(f"Card with id:{card_id} is not available")

            if result["cert_number"]:
                duplicate = self.db.execute(
                    "SELECT 1 FROM grading_submission_cards "
                    "WHERE cert_number IS NOT NULL "
                    "AND LOWER(TRIM(grader)) = LOWER(TRIM(?)) "
                    "AND LOWER(TRIM(cert_number)) = LOWER(TRIM(?))",
                    (result["grader"], result["cert_number"]),
                ).fetchone()
                if duplicate:
                    raise ValidationError(
                        {"cert_number": "Certificate is already assigned to another card"}
                    )

            self.db.execute(
                "INSERT INTO grading_submission_cards "
                "(card_id, grader, grade_numeric, grade_label, qualifier, cert_number, "
                "post_grade_market_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    card_id,
                    result["grader"],
                    _db_number(result["grade_numeric"]),
                    result["grade_label"],
                    result["qualifier"],
                    result["cert_number"],
                    _db_number(result["post_grade_market_value"]),
                ),
            )
            if result["post_grade_market_value"] is not None:
                self.db.execute(
                    "UPDATE cards SET market_value = ? WHERE id = ?",
                    (_db_number(result["post_grade_market_value"]), card_id),
                )
            self.db.commit()
            return None
        except Exception as error:
            self.db.rollback()
            return self._capture_error(error, "Failed to grade card | ")
