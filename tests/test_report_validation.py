from unittest.mock import MagicMock

import pytest
from flask import Flask

from tradeTracker import actions


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(actions.bp)
    return app


@pytest.mark.parametrize(
    ("query", "field"),
    [
        ("year=2026", "month"),
        ("month=8", "year"),
        ("month=0&year=2026", "month"),
        ("month=13&year=2026", "month"),
        ("month=8&year=1999", "year"),
        ("month=8&year=2101", "year"),
        ("month=nope&year=2026", "month"),
    ],
)
def test_generate_sold_report_validates_month_and_year(app, monkeypatch, query, field):
    get_db = MagicMock()
    monkeypatch.setattr(actions, "get_db", get_db)

    response = app.test_client().get(f"/generateSoldReport?{query}")

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
    assert field in response.get_json()["errors"]
    get_db.assert_not_called()
