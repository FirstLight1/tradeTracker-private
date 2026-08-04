import tradeTracker.services.models as models
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

            for card in submission.cards:
                available_card = self.db.execute(
                    'SELECT c.id FROM cards c WHERE c.id = ? AND c.sold_date IS NULL '
                    'AND NOT EXISTS ('
                    'SELECT 1 FROM grading_submission_cards gsc '
                    'WHERE gsc.card_id = c.id AND gsc.is_current = 1)',
                    (card.card_id,),
                ).fetchone()
                if not available_card:
                    raise ValueError(f'Card with id:{card.card_id} is not available')

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
                    'allocated_shared_cost, upcharge_fee, total_grading_cost, cert_number) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        submission_id, card.card_id, card.grader or submission.grader,
                        card.grading_fee, card.prep_fee, card.submitted_value,
                        shared_cost, card.upcharge, total_card_cost, None,
                    ),
                )

            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to create submission | " + str(e)

    def cancel_submission(self, submission_id: int) -> str | None:
        try:
            self.db.execute('UPDATE grading_submissions SET status = ? WHERE id = ?', (models.GradeStatus.CANCELLED, submission_id))
            self.db.execute('UPDATE grading_submission_cards SET is_current = 0 WHERE submission_id = ?', (submission_id,))
            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to cancel submission | " + str(e)

    def complete_submission(self, submission_id: int, items: list[models.GradingCompleteItems]) -> str | None:
        try:
            self.db.execute('BEGIN IMMEDIATE')
            for item in items:
                updated = self.db.execute(
                    'UPDATE grading_submission_cards SET grade_numeric = ?, grade_label = ?, '
                    'qualifier = ?, cert_number = ?, post_grade_market_value = ? '
                    'WHERE submission_id = ? AND card_id = ? AND is_current = 1',
                    (
                        item.grade_numeric, item.grade_label, item.qualifier,
                        item.cert_number, item.post_grade_market_value,
                        submission_id, item.card_id,
                    ),
                )
                if updated.rowcount != 1:
                    raise ValueError(
                        f'Card with id:{item.card_id} is not in submission {submission_id}'
                    )
                self.db.execute('UPDATE cards SET market_value = ? WHERE id = ?', (item.post_grade_market_value, item.card_id))

            self.db.execute('UPDATE grading_submissions SET status = ? WHERE id = ?', (models.GradeStatus.GRADED, submission_id))
            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to complete submission | " + str(e)

    def update_submission_status(self, submission_id: int, status: models.GradeStatus, notes: str | None = None) -> str | None:
        try:
            self.db.execute('UPDATE grading_submissions SET status = ?, notes = ? WHERE id = ?', (status, notes, submission_id))
            if status == models.GradeStatus.RETURNED or status == models.GradeStatus.CANCELLED:
                self.cancel_submission(submission_id)
            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to update submission | " + str(e)

    def grade_card(self, card_id: int, grade: models.GradingCompleteItems) -> str | None:
        try:
            self.db.execute('UPDATE grading_submission_cards SET grader = ?, grade_numeric = ?, grade_label = ?, qualifier = ?, cert_number = ?, post_grade_market_value = ? ',
                            (grade.grader, grade.grade_numeric, grade.grade_label, grade.qualifier, grade.cert_number, grade.post_grade_market_value))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            return "Failed to update submission | " + str(e)
        return None

