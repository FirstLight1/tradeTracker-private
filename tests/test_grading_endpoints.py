from unittest.mock import MagicMock

import pytest
from flask import Flask

from tradeTracker import grading
from tradeTracker.services.models import GradeStatus


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(grading.bp)
    return app


@pytest.fixture
def service(app, monkeypatch):
    service = MagicMock()
    db = object()
    monkeypatch.setattr(grading, "get_db", lambda: db)
    service_class = MagicMock(return_value=service)
    monkeypatch.setattr(grading, "GradingService", service_class)
    service.service_class = service_class
    service.db = db
    return service


def submission_payload():
    return {
        "submission": {
            "grader": "PSA",
            "service_level": "Regular",
            "status": "preparing",
            "submitted_at": "2026-07-29",
            "returned_at": None,
            "notes": "Batch",
            "outbound_shipping_cost": 10,
            "return_shipping_cost": 4,
            "insurance_cost": 3,
            "customs_duty_cost": 2,
            "other_shared_cost": 1,
        },
        "cards": [
            {
                "card_id": 7,
                "grader": None,
                "grading_fee": 20,
                "submitted_value": 100,
                "prep_fee": 2,
                "upcharge": 1,
            }
        ],
    }


def test_grading_page_renders_template(app, monkeypatch):
    monkeypatch.setattr(grading, "render_template", lambda name: name)

    response = app.test_client().get("/grading")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "grading.html"


def test_complete_grading_page_renders_for_submission(app, service, monkeypatch):
    render_template = MagicMock(return_value="completeGrading.html")
    monkeypatch.setattr(grading, "render_template", render_template)
    service.get_submission.return_value = {"id": 3, "status": "preparing"}

    response = app.test_client().get("/grading/submissions/3/complete")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "completeGrading.html"
    render_template.assert_called_once_with("completeGrading.html", submission_id=3)


@pytest.mark.parametrize("status", ["graded", "returned", "cancelled"])
def test_complete_grading_page_rejects_terminal_submission(app, service, status):
    service.get_submission.return_value = {"id": 3, "status": status}

    response = app.test_client().get("/grading/submissions/3/complete")

    assert response.status_code == 409


def test_get_submissions_returns_service_result(app, service):
    service.get_submissions.return_value = [{"id": 3, "status": "preparing"}]

    response = app.test_client().get("/grading/submissions")

    assert response.status_code == 200
    assert response.get_json() == [{"id": 3, "status": "preparing"}]
    service.service_class.assert_called_once_with(service.db)


def test_get_submission_returns_its_cards(app, service):
    service.get_submited_cards.return_value = [{"card_id": 7}]

    response = app.test_client().get("/grading/submissions/3")

    assert response.status_code == 200
    assert response.get_json() == [{"card_id": 7}]
    service.get_submited_cards.assert_called_once_with(3)


def test_create_submission_builds_models_from_json(app, service):
    service.create_submission.return_value = None

    response = app.test_client().post("/grading/submissions/create", json=submission_payload())

    assert response.status_code == 200
    assert response.get_json() == {"status": "success"}
    submission = service.create_submission.call_args.args[0]
    assert submission.grader == "PSA"
    assert submission.status == GradeStatus.PREPARING
    assert len(submission.cards) == 1
    assert submission.cards[0].card_id == 7
    assert submission.cards[0].prep_fee == 2


def test_create_submission_returns_service_error(app, service):
    service.create_submission.return_value = "database rejected submission"

    response = app.test_client().post("/grading/submissions/create", json=submission_payload())

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "message": "database rejected submission, Error code: Gx01",
    }


def test_cancel_submission_returns_service_result(app, service):
    service.cancel_submission.return_value = None

    response = app.test_client().post("/grading/submissions/3/cancel")

    assert response.status_code == 200
    assert response.get_json() == {"status": "success"}
    service.cancel_submission.assert_called_once_with(3)


def test_cancel_submission_returns_service_error(app, service):
    service.cancel_submission.return_value = "cancellation failed"

    response = app.test_client().post("/grading/submissions/3/cancel")

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "message": "cancellation failed, Error code: Gx02",
    }


def test_complete_submission_passes_every_item_to_service(app, service):
    service.complete_submission.return_value = None
    payload = [
        {
            "card_id": 7,
            "grade_numeric": 9,
            "grade_label": "Mint",
            "qualifier": None,
            "cert_number": "CERT-7",
            "post_grade_market_value": 180,
        },
        {
            "card_id": 8,
            "grade_numeric": 8.5,
            "grade_label": "NM-MT+",
            "qualifier": "OC",
            "cert_number": "CERT-8",
            "post_grade_market_value": 95,
        },
    ]

    response = app.test_client().post("/grading/submissions/3/complete", json=payload)

    assert response.status_code == 200
    completed_items = service.complete_submission.call_args.args[1]
    assert service.complete_submission.call_args.args[0] == 3
    assert [item.card_id for item in completed_items] == [7, 8]
    assert completed_items[1].qualifier == "OC"


def test_complete_submission_passes_nullable_fields_to_service_for_domain_validation(app, service):
    service.complete_submission.return_value = "A numeric grade or grade label is required"

    response = app.test_client().post(
        "/grading/submissions/3/complete",
        json=[
            {
                "card_id": 7,
                "grade_numeric": None,
                "grade_label": None,
                "qualifier": None,
                "cert_number": None,
                "post_grade_market_value": None,
            }
        ],
    )

    assert response.status_code == 400
    item = service.complete_submission.call_args.args[1][0]
    assert item.grade_numeric is None
    assert item.grade_label is None


def test_complete_submission_returns_service_error(app, service):
    service.complete_submission.return_value = "completion failed"

    response = app.test_client().post(
        "/grading/submissions/3/complete",
        json=[
            {
                "card_id": 7,
                "grade_numeric": 9,
                "grade_label": "Black Gem",
                "cert_number": "CERT-7",
                "post_grade_market_value": 180,
            }
        ],
    )

    assert response.status_code == 400
    assert response.get_json()["message"] == "completion failed, Error code: Gx04"


def test_update_submission_status_returns_service_error(app, service):
    service.update_submission_status.return_value = "status update failed"

    response = app.test_client().post(
        "/grading/submissions/3/updateStatus",
        json={"status": "received_by_grader"},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "message": "status update failed, Error code: Gx03",
    }


def test_update_submission_status_passes_return_details(app, service):
    service.update_submission_status.return_value = None

    response = app.test_client().post(
        "/grading/submissions/3/updateStatus",
        json={
            "status": "returned",
            "notes": "Carrier returned the shipment",
            "returned_at": "2026-08-13",
        },
    )

    assert response.status_code == 200
    service.update_submission_status.assert_called_once_with(
        3,
        GradeStatus.RETURNED,
        "Carrier returned the shipment",
        "2026-08-13",
    )


def test_update_submission_status_requires_return_details(app, service):
    response = app.test_client().post(
        "/grading/submissions/3/updateStatus",
        json={"status": "returned", "notes": " ", "returned_at": None},
    )

    assert response.status_code == 400
    assert response.get_json()["errors"] == {
        "notes": "Explain why the submission was returned",
        "returned_at": "Returned date is required",
    }
    service.update_submission_status.assert_not_called()


def test_direct_grade_rejects_blank_result(app, service):
    response = app.test_client().post(
        "/gradeCard",
        json={
            "card_id": 7,
            "grader": " ",
            "grade_numeric": None,
            "grade_label": None,
            "qualifier": None,
            "cert_number": None,
            "post_grade_market_value": None,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["errors"] == {
        "grader": "Grader is required",
        "grade_numeric": "Enter a numeric grade or a grade label",
    }
    service.grade_card.assert_not_called()


def test_create_submission_rejects_reversed_dates(app, service):
    payload = submission_payload()
    payload["submission"]["returned_at"] = "2020-01-01"

    response = app.test_client().post("/grading/submissions/create", json=payload)

    assert response.status_code == 400
    assert response.get_json()["errors"] == {
        "returned_at": "Active submissions cannot have a returned date"
    }
    service.create_submission.assert_not_called()


@pytest.mark.parametrize(
    ("path", "payload", "field"),
    [
        (
            "/grading/submissions/create",
            {
                **submission_payload(),
                "submission": {
                    **submission_payload()["submission"],
                    "outbound_shipping_cost": "1e100000",
                },
            },
            "outbound_shipping_cost",
        ),
        (
            "/grading/submissions/3/complete",
            [
                {
                    "card_id": 7,
                    "grade_numeric": 9,
                    "grade_label": "Mint",
                    "qualifier": None,
                    "cert_number": None,
                    "post_grade_market_value": "1e100000",
                }
            ],
            "post_grade_market_value",
        ),
        (
            "/gradeCard",
            {
                "card_id": 7,
                "grader": "PSA",
                "grade_numeric": 9,
                "grade_label": None,
                "qualifier": None,
                "cert_number": None,
                "post_grade_market_value": "1e100000",
            },
            "post_grade_market_value",
        ),
    ],
)
def test_grading_endpoints_reject_storage_overflow_values(app, service, path, payload, field):
    response = app.test_client().post(path, json=payload)

    assert response.status_code == 400
    assert field in response.get_json()["errors"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/grading"),
        ("post", "/grading/submissions"),
        ("post", "/grading/submissions/3"),
        ("get", "/grading/submissions/3/cancel"),
        ("get", "/grading/submissions/3/updateStatus"),
    ],
)
def test_endpoints_reject_unsupported_methods(app, method, path):
    response = getattr(app.test_client(), method)(path)

    assert response.status_code == 405


@pytest.mark.parametrize(
    ("path", "payload", "message", "error_field"),
    [
        ("/grading/submissions/create", {}, "Please correct the highlighted fields.", "submission"),
        ("/grading/submissions/3/complete", [], "Please correct the highlighted fields.", "cards"),
        (
            "/grading/submissions/3/updateStatus",
            {"status": "not-a-status"},
            "Invalid grading status payload",
            None,
        ),
    ],
)
def test_endpoints_reject_invalid_payloads(app, service, path, payload, message, error_field):
    response = app.test_client().post(path, json=payload)

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
    assert response.get_json()["message"] == message
    if error_field:
        assert error_field in response.get_json()["errors"]
    service.create_submission.assert_not_called()
    service.complete_submission.assert_not_called()
    service.update_submission_status.assert_not_called()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/grading", None),
        ("get", "/grading/submissions", None),
        ("get", "/grading/submissions/3", None),
        ("get", "/grading/submissions/3/complete", None),
        ("post", "/grading/submissions/create", submission_payload()),
        ("post", "/grading/submissions/3/cancel", None),
        ("post", "/grading/submissions/3/complete", []),
        (
            "post",
            "/grading/submissions/3/updateStatus",
            {"status": "preparing"},
        ),
    ],
)
def test_endpoints_require_authentication(app, monkeypatch, method, path, payload):
    monkeypatch.setenv("FLASK_ENV", "production")

    response = getattr(app.test_client(), method)(path, json=payload)

    assert response.status_code == 403
