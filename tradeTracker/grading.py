from tradeTracker.services.grading_service import GradingService
from tradeTracker.services.models import (
    GradingSubmission,
    GradingSubmissionCard,
    GradeStatus,
    GradingCompleteItems,
)
from tradeTracker.services.grading_validation import ValidationError
from tradeTracker.services.cfAuth import verify_token, require_api_token
from tradeTracker.db import get_db
from flask import request, Blueprint, jsonify, abort, render_template
import logging


bp = Blueprint("grading", __name__)
logger = logging.getLogger(__name__)


def validation_response(errors, message="Please correct the highlighted fields."):
    return jsonify({"status": "error", "message": message, "errors": errors}), 400


def json_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError({"_form": "Request body must be a JSON object"})
    return data


def service_validation_response(service):
    errors = getattr(service, "validation_errors", None)
    return validation_response(errors) if isinstance(errors, dict) and errors else None


@bp.route("/grading", methods=("GET",))
@verify_token
def grading_render():
    return render_template("grading.html")


@bp.route("/grading/submissions", methods=("GET",))
@verify_token
def grading():
    gs = GradingService(get_db())
    submission = gs.get_submissions()
    return jsonify(submission)


@bp.route("/grading/submissions/<int:submission_id>", methods=("GET",))
@verify_token
def get_submission(submission_id):
    gs = GradingService(get_db())
    cards = gs.get_submited_cards(submission_id)
    return jsonify(cards)


@bp.route("/grading/submissions/create", methods=("POST", "GET"))
@verify_token
def create_submission():
    if request.method == "GET":
        return render_template("createGrading.html")
    else:
        try:
            data = json_object()
            submission = data.get("submission")
            items = data.get("cards")
            grading_submission = GradingSubmission.from_dict(submission)
            grading_cards = [GradingSubmissionCard.from_dict(item) for item in items]
            if grading_submission.returned_at is not None:
                raise ValidationError(
                    {"returned_at": "Active submissions cannot have a returned date"}
                )
        except ValidationError as e:
            logger.warning("Invalid grading submission payload | reason: %s", e)
            return validation_response(e.errors)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Invalid grading submission payload | reason: %s", e)
            return jsonify(
                {"status": "error", "message": "Invalid grading submission payload"}
            ), 400

        grading_submission.cards = grading_cards
        gs = GradingService(get_db())
        err = gs.create_submission(grading_submission)
        if err:
            logger.warning("Failed to create grading submission | reason: %s", err)
            response = service_validation_response(gs)
            if response:
                return response
            return jsonify({"status": "error", "message": f"{err}, Error code: Gx01"}), 400
        logger.info(
            "Grading submission created successfully | grader: %s | card_count: %s",
            grading_submission.grader,
            len(grading_cards),
        )
        return jsonify({"status": "success"}), 200


@bp.route("/grading/submissions/<int:submission_id>/cancel", methods=("POST",))
@verify_token
def cancel_submission(submission_id):
    gs = GradingService(get_db())
    err = gs.cancel_submission(submission_id)

    if err:
        logger.warning(
            "Failed to cancel grading submission | submission_id: %s | reason: %s",
            submission_id,
            err,
        )
        response = service_validation_response(gs)
        if response:
            return response
        return jsonify({"status": "error", "message": f"{err}, Error code: Gx02"}), 400
    logger.info("Grading submission cancelled successfully | submission_id: %s", submission_id)
    return jsonify({"status": "success"}), 200


@bp.route("/grading/submissions/<int:submission_id>/complete", methods=("POST", "GET"))
@verify_token
def complete_submission(submission_id):
    if request.method == "GET":
        submission = GradingService(get_db()).get_submission(submission_id)
        if not submission:
            abort(404)
        if GradeStatus(submission["status"]).is_terminal:
            abort(409)
        return render_template("completeGrading.html", submission_id=submission_id)
    else:
        try:
            items = request.get_json(silent=True)
            completed_items = [GradingCompleteItems.from_dict(item) for item in items]
        except ValidationError as e:
            logger.warning(
                "Invalid grading completion payload | submission_id: %s | reason: %s",
                submission_id,
                e,
            )
            return validation_response(e.errors)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(
                "Invalid grading completion payload | submission_id: %s | reason: %s",
                submission_id,
                e,
            )
            return jsonify(
                {"status": "error", "message": "Invalid grading completion payload"}
            ), 400

        gs = GradingService(get_db())
        err = gs.complete_submission(submission_id, completed_items)

        if err:
            logger.warning(
                "Failed to complete grading submission | submission_id: %s | reason: %s",
                submission_id,
                err,
            )
            response = service_validation_response(gs)
            if response:
                return response
            return jsonify({"status": "error", "message": f"{err}, Error code: Gx04"}), 400
        logger.info(
            "Grading submission completed successfully | submission_id: %s | card_count: %s",
            submission_id,
            len(completed_items),
        )
        return jsonify({"status": "success"}), 200


@bp.route("/grading/submissions/<int:submission_id>/updateStatus", methods=("POST",))
@verify_token
def update_submission_status(submission_id):
    try:
        data = json_object()
        status = GradeStatus(data.get("status"))
        notes = data.get("notes")
        returned_at = data.get("returned_at")
        if status == GradeStatus.RETURNED:
            if not returned_at:
                raise ValidationError("Returned date is required")
    except ValidationError as e:
        logger.warning(
            "Invalid grading status payload | submission_id: %s | reason: %s",
            submission_id,
            e,
        )
        return validation_response(e.errors)
    except (TypeError, ValueError) as e:
        logger.warning(
            "Invalid grading status payload | submission_id: %s | reason: %s",
            submission_id,
            e,
        )
        return jsonify({"status": "error", "message": "Invalid grading status payload"}), 400

    gs = GradingService(get_db())
    err = gs.update_submission_status(submission_id, status, notes, returned_at)
    if err:
        logger.warning(
            "Failed to update grading submission status | submission_id: %s | status: %s | reason: %s",
            submission_id,
            status.value,
            err,
        )
        response = service_validation_response(gs)
        if response:
            return response
        return jsonify({"status": "error", "message": f"{err}, Error code: Gx03"}), 400
    logger.info(
        "Grading submission status updated successfully | submission_id: %s | status: %s",
        submission_id,
        status.value,
    )
    return jsonify({"status": "success"}), 200


@bp.route("/gradeCard", methods=("POST",))
@verify_token
def grade_card():
    try:
        data = json_object()
        grade = GradingCompleteItems.from_dict(data)
        errors = {}
        if not grade.grader:
            errors["grader"] = "Grader is required"
        if grade.grade_numeric is None and not grade.grade_label:
            errors["grade_numeric"] = "Enter a numeric grade or a grade label"
        if errors:
            raise ValidationError(errors)
    except ValidationError as e:
        logger.warning("Invalid card grading payload | reason: %s", e)
        return validation_response(e.errors)
    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Invalid card grading payload | reason: %s", e)
        return jsonify({"status": "error", "message": "Invalid card grading payload"}), 400

    gs = GradingService(get_db())
    err = gs.grade_card(grade.card_id, grade)
    if err:
        logger.warning("Failed to grade card | card_id: %s | reason: %s", grade.card_id, err)
        response = service_validation_response(gs)
        if response:
            return response
        return jsonify({"status": "error", "message": f"{err}, Error code: Gx05"}), 400

    return jsonify({"status": "success"})
