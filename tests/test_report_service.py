import sqlite3

from tradeTracker.services.pdf_utils import wrap_table_text
from tradeTracker.services.report_service import ReportService


def test_generate_sold_report_uses_monthly_data_and_writes_pdf(tmp_path):
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
        CREATE TABLE grading_submission_cards (
            card_id INTEGER,
            grader TEXT,
            grade_numeric REAL,
            is_current INTEGER
        );
        CREATE TABLE sealed (
            name TEXT,
            language TEXT,
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
        INSERT INTO grading_submission_cards VALUES (1, 'PSA', 9, 1);
        INSERT INTO sealed VALUES ('Booster Box', 'EN', 20, 30, 25, 2, 7, 1);
        INSERT INTO bulk_sales VALUES ('holo', 10, 5, 1);
        """
    )
    service = ReportService(db)

    pdf_path = tmp_path / "sold-report.pdf"
    result = service.generateSoldReport(None, None, "08", "2026", str(pdf_path))

    assert result == str(pdf_path)
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


def test_generate_purchase_report_returns_auction_name_and_pdf():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE auctions (id INTEGER PRIMARY KEY, auction_name TEXT, date_created TEXT);
        CREATE TABLE cards (
            auction_id INTEGER,
            card_name TEXT,
            card_num TEXT,
            condition TEXT,
            language TEXT,
            card_price REAL,
            market_value REAL,
            sold_date TEXT
        );
        CREATE TABLE sealed (
            auction_id INTEGER,
            name TEXT,
            price REAL,
            market_value REAL,
            sale_id INTEGER,
            opened INTEGER
        );
        CREATE TABLE bulk_items (auction_id INTEGER, item_type TEXT, quantity INTEGER);

        INSERT INTO auctions VALUES (7, 'Summer Auction', '2026-08-15T12:00:00');
        INSERT INTO cards VALUES (7, 'Pikachu', '025', 'NM', 'EN', 10, 15, NULL);
        INSERT INTO sealed VALUES (7, 'Booster Box', 20, 30, NULL, 0);
        INSERT INTO bulk_items VALUES (7, 'holo', 10);
        """
    )
    service = ReportService(db)

    auction_name, pdf = service.generatePurchaseReport(7)

    assert auction_name == "Summer Auction"
    assert pdf.startswith(b"%PDF")
