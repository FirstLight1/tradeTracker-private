import sqlite3

from tradeTracker.migration import createGradingTables


def test_create_grading_tables_is_idempotent(tmp_path):
    db_path = tmp_path / "grading.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE cards (id INTEGER PRIMARY KEY)")
    conn.close()

    createGradingTables(db_path)
    createGradingTables(db_path)

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'index' AND tbl_name = 'grading_submission_cards'"
            )
        }
        foreign_keys = {
            row[3]: (row[2], row[6])
            for row in conn.execute(
                "PRAGMA foreign_key_list(grading_submission_cards)"
            )
        }
    finally:
        conn.close()

    assert {"grading_submissions", "grading_submission_cards"} <= tables
    assert {
        "idx_grading_current_card",
        "idx_grading_submission_cards_submission",
        "idx_grading_submission_cards_card",
    } <= indexes
    assert foreign_keys == {
        "card_id": ("cards", "RESTRICT"),
        "submission_id": ("grading_submissions", "RESTRICT"),
    }


def test_create_grading_tables_completes_partial_migration(tmp_path):
    db_path = tmp_path / "partial-grading.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE cards (id INTEGER PRIMARY KEY)")
    conn.execute("""
        CREATE TABLE grading_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grader TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    createGradingTables(db_path)

    conn = sqlite3.connect(db_path)
    try:
        child_exists = conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'grading_submission_cards'"
        ).fetchone()
    finally:
        conn.close()

    assert child_exists == (1,)
