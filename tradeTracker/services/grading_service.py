import tradeTracker.services.models as models
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Any

class GradingService:
    def __init__(self, db):
        self.db = db

    def get_submissions(self) -> list[dict[str, Any]]:

        submissions = self.db.execute('SELECT * FROM grading_submissions ORDER BY id DESC').fetchall()
        return [dict(submission) for submission in submissions]
        

    def get_submited_cards(self, submission_id: int) -> list[dict[str, Any]]:
        cards = self.db.execute('SELECT * FROM grading_submission_cards gd JOIN cards c '
                                'ON gd.card_id = c.id '
                                'WHERE gd.submission_id = ?',
                                (submission_id,)).fetchall()

        return [dict(card) for card in cards]


    def create_submission(self, submission: models.GradingSubmission) -> str | None:
        try:
            self.db.execute('BEGIN IMMEDIATE')
            curr = self.db.cursor()
            if not submission.cards:
                raise ValueError('A submission must contain at least one card')

            total_submitted_value = sum(card.submitted_value for card in submission.cards)
            if total_submitted_value <= 0:
                raise ValueError('Total submitted value must be greater than zero')

            card_prices = {}
            for card in submission.cards:
                available_card = self.db.execute(
                    'SELECT c.id, c.card_price FROM cards c WHERE c.id = ? AND c.sold_date IS NULL '
                    'AND NOT EXISTS ('
                    'SELECT 1 FROM grading_submission_cards gsc '
                    'WHERE gsc.card_id = c.id AND gsc.is_current = 1)',
                    (card.card_id,),
                ).fetchone()
                if not available_card:
                    raise ValueError(f'Card with id:{card.card_id} is not available')
                card_prices[card.card_id] = available_card['card_price']

            curr.execute('INSERT INTO grading_submissions (grader, service_level, status, outbound_shipping_cost, return_shipping_cost, insurance_cost, customs_duty_cost, other_shared_cost, submitted_at, returned_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                            (submission.grader, submission.service_level, submission.status, submission.outbound_shipping_cost, submission.return_shipping_cost, submission.insurance_cost, submission.customs_duty_cost, submission.other_shared_cost, submission.submitted_at, submission.returned_at, submission.notes))

            submission_id = curr.lastrowid
            shared_cost_total = (
                submission.outbound_shipping_cost
                + submission.return_shipping_cost
                + submission.insurance_cost
                + submission.customs_duty_cost
                + submission.other_shared_cost
            )
            for card in submission.cards:
                shared_cost = shared_cost_total * card.submitted_value / total_submitted_value
                total_card_cost = shared_cost + card.grading_fee + card.prep_fee + card.upcharge
                curr.execute(
                    'INSERT INTO grading_submission_cards '
                    '(submission_id, card_id, grader, grading_fee, prep_fee, submitted_value, '
                    'allocated_shared_cost, upcharge_fee, total_grading_cost, landed_cost, cert_number) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        submission_id, card.card_id, card.grader or submission.grader,
                        card.grading_fee, card.prep_fee, card.submitted_value,
                        shared_cost, card.upcharge, total_card_cost,
                        (
                            card_prices[card.card_id] + total_card_cost
                            if card_prices[card.card_id] is not None
                            else None
                        ), None,
                    ),
                )

            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to create submission | " + str(e)

    def cancel_submission(self, submission_id: int) -> str | None:
        try:
            updated = self.db.execute(
                'UPDATE grading_submissions SET status = ? WHERE id = ? AND status != ?',
                (
                    models.GradeStatus.CANCELLED,
                    submission_id,
                    models.GradeStatus.GRADED,
                ),
            )
            if updated.rowcount != 1:
                existing = self.db.execute(
                    'SELECT status FROM grading_submissions WHERE id = ?',
                    (submission_id,),
                ).fetchone()
                if not existing:
                    raise ValueError(f'Submission with id:{submission_id} was not found')
                raise ValueError('Submission is already finalized')
            self.db.execute('UPDATE grading_submission_cards SET is_current = 0 WHERE submission_id = ?', (submission_id,))
            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to cancel submission | " + str(e)

    def complete_submission(self, submission_id: int, items: list[models.GradingCompleteItems]) -> str | None:
        try:
            self.db.execute('BEGIN IMMEDIATE')
            submission = self.db.execute(
                'SELECT status, outbound_shipping_cost, return_shipping_cost, insurance_cost, '
                'customs_duty_cost, other_shared_cost FROM grading_submissions WHERE id = ?',
                (submission_id,),
            ).fetchone()
            cost_rows = self.db.execute(
                'SELECT gsc.card_id, gsc.submitted_value, gsc.grading_fee, gsc.prep_fee, '
                'gsc.upcharge_fee, c.card_price FROM grading_submission_cards gsc '
                'JOIN cards c ON c.id = gsc.card_id '
                'WHERE gsc.submission_id = ? AND gsc.is_current = 1 ORDER BY gsc.card_id',
                (submission_id,),
            ).fetchall()
            expected_card_ids = {row['card_id'] for row in cost_rows}
            completed_card_ids = {item.card_id for item in items}
            if (
                not submission
                or not expected_card_ids
                or completed_card_ids != expected_card_ids
                or len(items) != len(expected_card_ids)
            ):
                raise ValueError('Completion must include every card in the submission')
            if submission['status'] == models.GradeStatus.GRADED:
                raise ValueError('Submission is already finalized')

            cent = Decimal('0.01')
            as_decimal = lambda value: Decimal(str(value or 0))
            shared_total = sum(
                (
                    as_decimal(submission[column])
                    for column in (
                        'outbound_shipping_cost', 'return_shipping_cost', 'insurance_cost',
                        'customs_duty_cost', 'other_shared_cost',
                    )
                ),
                Decimal('0'),
            ).quantize(cent, rounding=ROUND_HALF_UP)
            submitted_total = sum(
                (as_decimal(row['submitted_value']) for row in cost_rows),
                Decimal('0'),
            )
            if submitted_total > 0:
                exact_allocations = [
                    shared_total * as_decimal(row['submitted_value']) / submitted_total
                    for row in cost_rows
                ]
            else:
                exact_allocations = [
                    shared_total / Decimal(len(cost_rows))
                    for _ in cost_rows
                ]
            allocations = [
                allocation.quantize(cent, rounding=ROUND_DOWN)
                for allocation in exact_allocations
            ]
            remainder_cents = int((shared_total - sum(allocations)) / cent)
            remainder_order = sorted(
                range(len(cost_rows)),
                key=lambda index: (exact_allocations[index] - allocations[index], -index),
                reverse=True,
            )
            for index in remainder_order[:remainder_cents]:
                allocations[index] += cent

            finalized_costs = {}
            for index, row in enumerate(cost_rows):
                allocated_shared_cost = allocations[index]
                direct_cost = sum(
                    (
                        as_decimal(row[column])
                        for column in ('grading_fee', 'prep_fee', 'upcharge_fee')
                    ),
                    Decimal('0'),
                )
                total_grading_cost = (direct_cost + allocated_shared_cost).quantize(
                    cent, rounding=ROUND_HALF_UP
                )
                landed_cost = (
                    (as_decimal(row['card_price']) + total_grading_cost).quantize(
                        cent, rounding=ROUND_HALF_UP
                    )
                    if row['card_price'] is not None
                    else None
                )
                finalized_costs[row['card_id']] = (
                    float(allocated_shared_cost),
                    float(total_grading_cost),
                    float(landed_cost) if landed_cost is not None else None,
                )

            for item in items:
                allocated_shared_cost, total_grading_cost, landed_cost = finalized_costs[item.card_id]
                updated = self.db.execute(
                    'UPDATE grading_submission_cards SET grade_numeric = ?, grade_label = ?, '
                    'qualifier = ?, cert_number = ?, post_grade_market_value = ?, '
                    'allocated_shared_cost = ?, total_grading_cost = ?, landed_cost = ? '
                    'WHERE submission_id = ? AND card_id = ? AND is_current = 1',
                    (
                        item.grade_numeric, item.grade_label, item.qualifier,
                        item.cert_number, item.post_grade_market_value,
                        allocated_shared_cost, total_grading_cost, landed_cost,
                        submission_id, item.card_id,
                    ),
                )
                if updated.rowcount != 1:
                    raise ValueError(
                        f'Card with id:{item.card_id} is not in submission {submission_id}'
                    )
                if item.post_grade_market_value is not None:
                    self.db.execute(
                        'UPDATE cards SET market_value = ? WHERE id = ?',
                        (item.post_grade_market_value, item.card_id),
                    )

            self.db.execute('UPDATE grading_submissions SET status = ? WHERE id = ?', (models.GradeStatus.GRADED, submission_id))
            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to complete submission | " + str(e)

    def update_submission_status(self, submission_id: int, status: models.GradeStatus, notes: str | None = None) -> str | None:
        try:
            current = self.db.execute(
                'SELECT status FROM grading_submissions WHERE id = ?',
                (submission_id,),
            ).fetchone()
            if not current:
                raise ValueError(f'Submission with id:{submission_id} was not found')
            if current['status'] == models.GradeStatus.GRADED:
                raise ValueError('Submission is already finalized')
            if status == models.GradeStatus.GRADED:
                raise ValueError('Use complete_submission to mark a submission graded')
            updated = self.db.execute(
                'UPDATE grading_submissions SET status = ?, notes = ? '
                'WHERE id = ? AND status != ?',
                (status, notes, submission_id, models.GradeStatus.GRADED),
            )
            if updated.rowcount != 1:
                raise ValueError('Submission is already finalized')
            if status == models.GradeStatus.RETURNED or status == models.GradeStatus.CANCELLED:
                self.cancel_submission(submission_id)
            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to update submission | " + str(e)

    def grade_card(self, card_id: int, grade: models.GradingCompleteItems) -> str | None:
        try:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute("INSERT INTO grading_submission_cards(card_id, grader, grade_numeric, grade_label, qualifier, cert_number, post_grade_market_value) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    card_id, grade.grader, grade.grade_numeric, grade.grade_label, grade.qualifier,
                    grade.cert_number, grade.post_grade_market_value, 
                ))
            if grade.post_grade_market_value is not None:
                self.db.execute(
                    'UPDATE cards SET market_value = ? WHERE id = ?',
                    (grade.post_grade_market_value, card_id),
                )
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            return "Failed to grade card | " + str(e)
        return None

