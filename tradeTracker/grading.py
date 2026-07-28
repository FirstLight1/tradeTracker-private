from tradeTracker.services.grading_service import GradingService
from tradeTracker.services.models import GradingSubmission, GradingSubmissionCard, GradeStatus, GradingCompleteItems
from tradeTracker.services.cfAuth import verify_token, require_api_token
from tradeTracker.db import get_db
import datetime
from flask import request, Blueprint, jsonify, current_app, send_file, abort, render_template
import logging


bp = Blueprint('grading', __name__)
logger = logging.getLogger(__name__)

@bp.route('/grading', methods=('POST',))
@verify_token
def grading():
    return render_template("grading.html")

@bp.route('/grading/submissions', methods=('GET',))
@verify_token
def grading():
    gs = GradingService(get_db())
    submission = gs.get_submissions()
    return jsonify(submission)


@bp.route('/grading/submissions/<int:submission_id>', methods=('GET',))
@verify_token
def get_submission(submission_id):
    gs = GradingService(get_db())
    cards = gs.get_submited_cards(submission_id)
    return jsonify(cards)

@bp.route('/grading/submissions/<int:submission_id>/create', methods=('POST',))
def create_submission(submission_id):
    gs = GradingService(get_db())
    submission = request.get_json()
    items = submission.get('cards')

    grading_submission = GradingSubmission()

    grading_cards = []
    for item in items:
        card = GradingSubmissionCard()
        grading_cards.append(card)

    err = gs.complete_submission(grading_submission, grading_cards)
    if err:
        return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx01'}), 400
    return jsonify({'status': 'success'}), 200

@bp.route('/grading/submissions/<int:submission_id>/complete', methods=('POST',))
def complete_submission(submission_id):
    gs = GradingService(get_db())
    gs.complete_submission(submission_id, request.get_json())
