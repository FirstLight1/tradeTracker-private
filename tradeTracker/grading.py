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

@bp.route('/grading/submissions/create', methods=('POST','GET'))
@verify_token
def create_submission():
    if request.method == 'GET':
        return render_template("createGrading.html")
    else:
        data = request.get_json()

        submission = data.get('submission')
        items = data.get('cards')

        try:
            grading_submission = GradingSubmission.from_dict(submission)
            grading_cards = [GradingSubmissionCard.from_dict(item) for item in items]
        except (KeyError, TypeError, ValueError) as e:
            logger.warning('Invalid grading submission payload | reason: %s', e)
            return jsonify({'status': 'error', 'message': 'Invalid grading submission payload'}), 400

        grading_submission.cards = grading_cards
        gs = GradingService(get_db())
        err = gs.create_submission(grading_submission)
        if err:
            logger.warning('Failed to create grading submission | reason: %s', err)
            return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx01'}), 400
        logger.info(
            'Grading submission created successfully | grader: %s | card_count: %s',
            grading_submission.grader,
            len(grading_cards),
        )
        return jsonify({'status': 'success'}), 200

@bp.route('/grading/submissions/<int:submission_id>/cancel', methods=('POST',))
@verify_token
def cancel_submission(submission_id):
    gs = GradingService(get_db())
    err =  gs.cancel_submission(submission_id)
  
    if err:
        logger.warning(
            'Failed to cancel grading submission | submission_id: %s | reason: %s',
            submission_id,
            err,
        )
        return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx02'}), 400
    logger.info('Grading submission cancelled successfully | submission_id: %s', submission_id)
    return jsonify({'status': 'success'}), 200


@bp.route('/grading/submissions/<int:submission_id>/complete', methods=('POST','GET'))
@verify_token
def complete_submission(submission_id):
    if request.method == 'GET':
        return render_template("completeGrading.html", submission_id=submission_id)
    else:
        items = request.get_json()

        try:
            if not items:
                raise ValueError('A completion payload must contain at least one card')
            completed_items = [GradingCompleteItems.from_dict(item) for item in items]
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(
                'Invalid grading completion payload | submission_id: %s | reason: %s',
                submission_id,
                e,
            )
            return jsonify({'status': 'error', 'message': 'Invalid grading completion payload'}), 400

        gs = GradingService(get_db())
        err = gs.complete_submission(submission_id, completed_items)

        if err:
            logger.warning(
                'Failed to complete grading submission | submission_id: %s | reason: %s',
                submission_id,
                err,
            )
            return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx04'}), 400
        logger.info(
            'Grading submission completed successfully | submission_id: %s | card_count: %s',
            submission_id,
            len(completed_items),
        )
        return jsonify({'status': 'success'}), 200

@bp.route('/grading/submissions/<int:submission_id>/updateStatus', methods=('POST',))
@verify_token
def update_submission_status(submission_id):
    data = request.get_json()

    try:
        status = GradeStatus(data.get('status'))
    except (TypeError, ValueError) as e:
        logger.warning(
            'Invalid grading status payload | submission_id: %s | reason: %s',
            submission_id,
            e,
        )
        return jsonify({'status': 'error', 'message': 'Invalid grading status payload'}), 400

    gs = GradingService(get_db())
    err =  gs.update_submission_status(submission_id, status, data.get('notes', None))
    if err:
        logger.warning(
            'Failed to update grading submission status | submission_id: %s | status: %s | reason: %s',
            submission_id,
            status.value,
            err,
        )
        return jsonify({'status': 'error', 'message': f'{err}, Error code: Gx03'}), 400
    logger.info(
        'Grading submission status updated successfully | submission_id: %s | status: %s',
        submission_id,
        status.value,
    )
    return jsonify({'status': 'success'}), 200


