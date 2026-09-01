import sqlite3

from tradeTracker.services.pdf_utils import wrap_table_text
from tradeTracker.services.report_service import ReportService


def test_get_sold_data_returns_dictionary_rows_and_generates_pdf(tmp_path):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE sales (id INTEGER PRIMARY KEY, sale_date TEXT, shipping_info REAL);
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY,
            card_name TEXT,
            card_num TEXT,
            card_price REAL,
            language TEXT
        );
        CREATE TABLE sale_items (card_id INTEGER, sale_id INTEGER, sell_price REAL);
        CREATE TABLE grading_submission_cards (card_id INTEGER, is_current INTEGER);
        CREATE TABLE sealed (
            name TEXT,
            price REAL,
            sell_price REAL,
            market_value REAL,
            quantity INTEGER,
            auction_id INTEGER,
            sale_id INTEGER
        );
        CREATE TABLE bulk_sales (
            item_type TEXT,
            quantity INTEGER,
            total_price REAL,
            sale_id INTEGER
        );

        INSERT INTO sales VALUES (1, '2026-08-15', 4.5);
        INSERT INTO cards VALUES (1, 'Pikachu', '025', 10, 'EN');
        INSERT INTO sale_items VALUES (1, 1, 15);
        INSERT INTO grading_submission_cards VALUES (1, 1);
        INSERT INTO sealed VALUES ('Booster Box', 20, 30, 25, 2, 7, 1);
        INSERT INTO bulk_sales VALUES ('holo', 10, 5, 1);
        """
    )
    service = ReportService(db)

    data = service._get_sold_data_month("08", "2026")

    assert all(isinstance(row, dict) for rows in data.values() for row in rows)
    assert list(data["items"][0]) == [
        "name",
        "item_num",
        "buy_price",
        "language",
        "sell_price",
        "sale_date",
        "is_graded",
        "item_type",
        "quantity",
        "auction_id",
    ]
    assert data["items"][0]["buy_price"] == 10
    assert data["items"][0]["is_graded"] == "True"
    assert data["shipping"] == [{"shipping_info": 4.5}]

    pdf_path = tmp_path / "sold-report.pdf"
    service.generatePurchaseReport(None, None, "08", "2026", str(pdf_path))

    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_wrap_table_text_builds_header_and_values_from_dictionaries():
    wrapped = wrap_table_text(
        [{"item_name": "Pikachu", "buy_price": 10}, {"item_name": "Mew", "buy_price": 12}],
        font_name="Helvetica",
    )

    assert [[cell.getPlainText() if hasattr(cell, "getPlainText") else cell for cell in row] for row in wrapped] == [
        ["item name", "buy price"],
        ["Pikachu", 10],
        ["Mew", 12],
    ]


def test_calculate_header_accepts_dictionary_rows_without_mutating_them():
    service = ReportService.__new__(ReportService)
    items = [
        {
            "item_type": "card",
            "buy_price": 10,
            "sell_price": 15,
            "quantity": 1,
            "auction_id": None,
        },
        {
            "item_type": "sealed",
            "buy_price": 20,
            "sell_price": 30,
            "quantity": 2,
            "auction_id": 7,
        },
    ]

    header = service._calculate_header(items, [])

    assert len(items) == 2
    assert header["card_count"] == 1
    assert header["sealed_count"] == 1
    assert header["total_buy_price"] == 50
    assert header["total_sell_price"] == 75
