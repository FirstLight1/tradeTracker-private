import tradeTracker.services.models as models
from datetime import datetime
import tradeTracker.CONSTANTS as CONSTANTS
from typing import Any

class GradingService:
    def __init__(self, db):
        self.db = db

    def get_submissions(self) -> list[dict[str, Any]]:

        submissions = self.db.execute('SELECT * FROM grading_submissions ').fetchall()
        return [dict(submission) for submission in submissions]
        

    def get_submited_cards(self, submission_id: int) -> list[dict[str, Any]]:
        cards = self.db.execute('SELECT * FROM grading_cards gd JOIN cards c '
                                'ON gd.card_id = c.id '
                                'WHERE gd.submission_id = ? AND',
                                (submission_id,)).fetchall()

        return [dict(card) for card in cards]


    def create_submission(self, submission: models.GradingSubmission) -> str | None:
        self.db.execute('BEGIN IMMEDIATE')
        curr = self.db.cursor()
        try: 
            curr.execute('INSERT INTO grading_submissions (grader, service_level, status, outbound_shipping_cost, return_shipping_cost, insurance_cost, customs_duty_cost, other_shared_cost, submitted_at, returned_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                            (submission.grader, submission.service_level, submission.status, submission.outbound_shipping_cost, submission.return_shipping_cost, submission.insurance_cost, submission.customs_duty_cost, submission.other_shared_cost, submission.submitted_at, submission.returned_at, submission.notes))

            submission_id = curr.lastrowid
        except Exception as e:
            self.db.rollback()
            return "Failed to create submission | " + str(e)
        
        total_grading_cost = submission.outbound_shipping_cost + submission.return_shipping_cost + submission.insurance_cost + submission.customs_duty_cost + submission.other_shared_cost
        total_submitted_value = sum([card.submitted_value for card in submission.cards])
        try:
            cards = submission.cards
            for card in cards:
                existing_card = self.db.execute('SELECT * FROM grading_cards WHERE card_id = ? AND sold_date IS NULL', (card.card_id,)).fetchone()
                if not existing_card:
                    return f'Failed to create grading submission card | Card with id:{card.card_id} not found'

                shared_cost = total_grading_cost * card.submitted_value / total_submitted_value 
                total_grading_cost = shared_cost + card.grading_fee + card.prep_fee + card.upcharge
                curr.execute('INSERT INTO grading_cards (submission_id, card_id, grader, grading_fee, submitted_value, allocated_shared_cost, upcharge_fee, total_grading_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                            (submission_id, card.card_id, card.grader, card.grading_fee, card.submitted_value, shared_cost ,card.upcharge, total_grading_cost))
        except Exception as e:
            self.db.rollback()
            return "Failed to create cards | " + str(e)
        
        self.db.commit()
        return None

    def cancel_submission(self, submission_id: int) -> str | None:
        try:
            self.db.execute('UPDATE grading_submissions SET status = ? WHERE submission_id = ?', (models.GradeStatus.CANCELLED, submission_id))
            self.db.execute('UPDATE grading_submissions_cards SET is_current = 0 WHERE submission_id = ?', (submission_id,))
            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to cancel submission | " + str(e)

    def complete_submission(self, submission_id: int, items: list[models.GradingCompleteItems]) -> str | None:
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('UPDATE grading_submissions SET status = ? WHERE submission_id = ?', (models.GradeStatus.GRADED, submission_id))
           
            for item in items:
                self.db.execute('INSERT INTO grading_complete_items (submission_id, card_id, grade_numeric, grade_label, qualifier, cert_number, post_grade_market_value) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                (submission_id, item.card_id, item.grade_numeric, item.grade_label, item.qualifier, item.cert_number, item.post_grade_market_value))
                self.db.execute('UPDATE cards SET market_value = ? WHERE id = ?', (item.post_grade_market_value, item.card_id))

            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to complete submission | " + str(e)

    def update_submission_status(self, submission_id: int, status: models.GradeStatus, notes: str | None = None) -> str | None:
        try:
            self.db.execute('UPDATE grading_submissions SET status = ?, notes = ? WHERE submission_id = ?', (status, notes, submission_id))
            self.db.commit()
            return None
        except Exception as e:
            self.db.rollback()
            return "Failed to update submission | " + str(e)

