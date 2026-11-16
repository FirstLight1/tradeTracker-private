import datetime
from unittest.mock import MagicMock

import pytest
from flask import Flask

from tradeTracker import actions
from tradeTracker.services.models import ItemInput, ItemType


def item_payload(**changes):
    return {
        "id": None,
        "item_type": "card",
        "name": "Flabébé",
        "normalized_name": "untrusted client value",
        "number": " 123 ",
        "condition": "Near Mint",
        "lang": "en",
        "buy_price": 1.25,
        "market_value": 2.50,
        "sell_price": None,
        "quantity": 1,
        "date": "2026-11-16",
        "cardmarketId": "12345",
        **changes,
    }


@pytest.mark.parametrize("item_type", ["card", "sealed"])
def test_item_input_accepts_matching_client_fields(item_type):
    item = ItemInput.from_dict(item_payload(item_type=item_type))

    assert item.id is None
    assert item.item_type == ItemType(item_type)
    assert item.name == "Flabébé"
    assert item.normalized_name == "FLABEBE"
    assert item.number == "123"
    assert item.lang == "en"
    assert item.buy_price == 1.25
    assert item.market_value == 2.50
    assert item.sell_price is None
    assert item.date == "2026-11-16"
    assert item.cardmarketId == "12345"


def test_item_input_accepts_nullable_fields_and_defaults():
    item = ItemInput.from_dict({"item_type": "sealed", "name": "Tin"})

    assert item.id is None
    assert item.number is None
    assert item.buy_price is None
    assert item.market_value is None
    assert item.sell_price is None
    assert item.quantity == 1
    assert item.date == datetime.date.today().isoformat()


def test_item_input_preserves_existing_snake_case_request_fields():
    item = ItemInput.from_dict({
        "id": "7", "item_type": "card", "card_name": "Pikachu",
        "card_number": "25", "language": "en",
    })

    assert item.id == 7
    assert item.name == "Pikachu"
    assert item.number == "25"
    assert item.lang == "en"


@pytest.mark.parametrize("route", ["/add", "/addToSingles"])
def test_creation_routes_pass_item_models_to_inventory_service(monkeypatch, route):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(actions.bp)
    service = MagicMock()
    service.create_auction_with_items.return_value = 2
    monkeypatch.setattr(actions, "get_db", lambda: object())
    monkeypatch.setattr(actions, "InventoryService", lambda db: service)
    payload = [item_payload()]
    if route == "/add":
        payload = {
            "auction": {"name": "Auction", "buy_price": 1.25, "date": "2026-11-16"},
            "cards": payload,
        }

    response = app.test_client().post(route, json=payload)

    assert response.status_code == 201
    call = (service.create_auction_with_items if route == "/add"
            else service.add_items_to_auction).call_args
    assert isinstance(call.args[1][0], ItemInput)
    assert call.args[1][0].normalized_name == "FLABEBE"


def test_existing_auction_accepts_matching_client_fields(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(actions.bp)
    db = MagicMock()
    monkeypatch.setattr(actions, "get_db", lambda: db)

    response = app.test_client().post(
        "/addToExistingAuction/2", json={"cards": [item_payload()]},
    )

    assert response.status_code == 201
    values = db.execute.call_args.args[1]
    assert values == ("Flabébé", "FLABEBE", " 123 ", "Near Mint", "en", 1.25, 2.50, 2, "12345")
    db.commit.assert_called_once()


@pytest.mark.parametrize("auction_id", [0, 2])
def test_open_sealed_accepts_matching_client_fields(monkeypatch, auction_id):
    monkeypatch.setenv("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(actions.bp)
    db = MagicMock()
    service = MagicMock()
    monkeypatch.setattr(actions, "get_db", lambda: db)
    monkeypatch.setattr(actions, "InventoryService", lambda db: service)

    response = app.test_client().post(
        f"/openSealed/{auction_id}", json={
            "openedItem": {"id": "s10", "initialValue": 2},
            "cards": [item_payload()],
            "sealed": [item_payload(item_type="sealed", name="Tin", number=None)],
        },
    )

    assert response.status_code == 200
    inserts = db.cursor.return_value.execute.call_args_list
    card_insert = next(call for call in inserts if "INSERT INTO cards" in call.args[0])
    sealed_insert = next(call for call in inserts if "INSERT INTO sealed" in call.args[0])
    assert card_insert.args[1][:5] == ("Flabébé", "FLABEBE", " 123 ", "Near Mint", "en")
    assert sealed_insert.args[1][:4] == ("Tin", "TIN", 1, "en")
    assert card_insert.args[1][5:7] == (1, 2.5)
    assert sealed_insert.args[1][4:6] == (1, 2.5)
    service.mark_sealed_opened.assert_called_once()
    db.commit.assert_called_once()
