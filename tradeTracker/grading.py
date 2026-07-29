from tradeTracker.services.grading_service import GradingService
from tradeTracker.services.models import GradingSubmission, GradingSubmissionCard, GradeStatus, GradingCompleteItems
from tradeTracker.services.cfAuth import verify_token, require_api_token
from tradeTracker.db import get_db
import datetime
from flask import request, Blueprint, jsonify, current_app, send_file, abort, render_template
import logging


bp = Blueprint('grading', __name__)
logger = logging.getLogger(__name__)

@bp.route('/grading', methods=('GET',))
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

@bp.route('/grading/submissions/create', methods=('POST',))
@verify_token
def create_submission():
    data = request.get_json()

    submission = data.get('submission')
    items = data.get('cards')

    try:
        grading_submission = GradingSubmission.from_dict(submission)
        grading_cards = [GradingSubmissionCard.from_dict(item) for item in items]
    except (KeyError, TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid grading submission payload'}), 400

    grading_submission.cards = grading_cards
    gs = GradingService(get_db())
    err = gs.create_submission(grading_submission)
    if err:
        return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx01'}), 400
    return jsonify({'status': 'success'}), 200

@bp.route('/grading/submissions/<int:submission_id>/cancel', methods=('POST',))
@verify_token
def cancel_submission(submission_id):
    gs = GradingService(get_db())
    err =  gs.cancel_submission(submission_id)
  
    if err:
        return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx02'}), 400
    return jsonify({'status': 'success'}), 200


@bp.route('/grading/submissions/<int:submission_id>/complete', methods=('POST',))
@verify_token
def complete_submission(submission_id):
    items = request.get_json()

    try:
        if not items:
            raise ValueError('A completion payload must contain at least one card')
        completed_items = [GradingCompleteItems.from_dict(item) for item in items]
    except (KeyError, TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid grading completion payload'}), 400

    gs = GradingService(get_db())
    err = gs.complete_submission(submission_id, completed_items)

    if err:
        return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx04'}), 400
    return jsonify({'status': 'success'}), 200

@bp.route('/grading/submissions/<int:submission_id>/updateStatus', methods=('POST',))
@verify_token
def update_submission_status(submission_id):
    data = request.get_json()

    try:
        status = GradeStatus(data.get('status'))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid grading status payload'}), 400

    gs = GradingService(get_db())
    err =  gs.update_submission_status(submission_id, status, data.get('notes', None))
    if err:
        return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx03'}), 400
    return jsonify({'status': 'success'}), 200


