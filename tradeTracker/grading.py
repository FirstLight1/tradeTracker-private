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
def grading_render():
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
    data = request.get_json()
    submission = data.get('submission')
    items = data.get('cards')

    grading_submission = GradingSubmission.from_dict(submission)

    grading_cards = []
    for item in items:
        card = GradingSubmissionCard.from_dict(item)
        grading_cards.append(card)

    grading_submission.cards = grading_cards
    err = gs.create_submission(grading_submission)
    if err:
        return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx01'}), 400
    return jsonify({'status': 'success'}), 200

@bp.route('/grading/submissions/<int:submission_id>/cancel', methods=('GET',))
def cancel_submission(submission_id):
    gs = GradingService(get_db())
    err =  gs.cancel_submission(submission_id)
  
    if err:
        return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx02'}), 400
    return jsonify({'status': 'success'}), 200


@bp.route('/grading/submissions/<int:submission_id>/complete', methods=('POST',))
def complete_submission(submission_id):
    gs = GradingService(get_db())
    items = request.get_json()
    completed_items = []
    for item in items:
        complete = GradingCompleteItems.from_dict(item)
    gs.complete_submission(submission_id,completed_items) 

    return jsonify({'status': 'success'}), 200

@bp.route('/grading/submissions/<int:submission_id>/updateStatus', methods=('POST',))
def update_submission_status(submission_id):
    data = request.get_json()
    gs = GradingService(get_db())
    status = GradeStatus(data.get('status'))

    err =  gs.update_submission_status(submission_id, status, data.get('notes', None))
    if err:
        return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx03'}), 400
    return jsonify({'status': 'success'}), 200


