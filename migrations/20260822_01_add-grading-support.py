"""Add the grading schema and graded-sale cost snapshots."""

from yoyo import step


__depends__ = {"20260812_01_u4Gpx-baseline-migrations"}


def add_graded_sale_costs(connection):
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(sale_items)")
    }
    if not columns:
        return

    added_internal_cost = "internal_cost" not in columns
    added_internal_profit = "internal_profit" not in columns

    if added_internal_cost:
        connection.execute("ALTER TABLE sale_items ADD COLUMN internal_cost REAL")
        connection.execute(
            "UPDATE sale_items SET internal_cost = "
            "(SELECT card_price FROM cards WHERE cards.id = sale_items.card_id)"
        )
    if added_internal_profit:
        connection.execute("ALTER TABLE sale_items ADD COLUMN internal_profit REAL")
        connection.execute("UPDATE sale_items SET internal_profit = profit")


steps = [
    step(
        """
        CREATE TABLE IF NOT EXISTS grading_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grader TEXT NOT NULL,
            service_level TEXT,
            status TEXT NOT NULL DEFAULT 'DRAFT',
            outbound_shipping_cost REAL NOT NULL DEFAULT 0,
            return_shipping_cost REAL NOT NULL DEFAULT 0,
            insurance_cost REAL NOT NULL DEFAULT 0,
            customs_duty_cost REAL NOT NULL DEFAULT 0,
            other_shared_cost REAL NOT NULL DEFAULT 0,
            submitted_at TEXT,
            returned_at TEXT,
            notes TEXT
        )
        """
    ),
    step(
        """
        CREATE TABLE IF NOT EXISTS grading_submission_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER,
            card_id INTEGER NOT NULL,
            grader TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 1,
            submitted_value REAL NOT NULL DEFAULT 0,
            grading_fee REAL NOT NULL DEFAULT 0,
            prep_fee REAL DEFAULT 0,
            upcharge_fee REAL DEFAULT 0,
            allocated_shared_cost REAL DEFAULT 0,
            total_grading_cost REAL NOT NULL DEFAULT 0,
            landed_cost REAL,
            grade_numeric REAL,
            grade_label TEXT,
            qualifier TEXT,
            cert_number TEXT COLLATE NOCASE DEFAULT '',
            post_grade_market_value REAL,
            notes TEXT,
            FOREIGN KEY (submission_id) REFERENCES grading_submissions(id) ON DELETE RESTRICT,
            FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE RESTRICT,
            UNIQUE (submission_id, card_id),
            UNIQUE (grader, cert_number)
        )
        """
    ),
    step(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_grading_current_card
        ON grading_submission_cards(card_id)
        WHERE is_current = 1
        """
    ),
    step(
        """
        CREATE INDEX IF NOT EXISTS idx_grading_submission_cards_submission
        ON grading_submission_cards(submission_id)
        """
    ),
    step(
        """
        CREATE INDEX IF NOT EXISTS idx_grading_submission_cards_card
        ON grading_submission_cards(card_id)
        """
    ),
    step(add_graded_sale_costs),
]
