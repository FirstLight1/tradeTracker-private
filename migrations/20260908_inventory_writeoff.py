"""
Inventory write off
"""

from yoyo import step

__depends__ = {}

steps = [
    step(
        "ALTER TABLE cards ADD COLUMN disposal_reason TEXT NULL",
        "ALTER TABLE cards DROP COLUMN disposal_reason",
    ),
    step(
        "ALTER TABLE cards ADD COLUMN disposal_date TEXT NULL",
        "ALTER TABLE cards DROP COLUMN disposal_date",
    ),
    step(
        "ALTER TABLE cards ADD COLUMN disposal_note TEXT NULL",
        "ALTER TABLE cards DROP COLUMN disposal_note",
    ),
    step(
        "ALTER TABLE sealed ADD COLUMN disposal_reason TEXT NULL",
        "ALTER TABLE sealed DROP COLUMN disposal_reason",
    ),
    step(
        "ALTER TABLE sealed ADD COLUMN disposal_date TEXT NULL",
        "ALTER TABLE sealed DROP COLUMN disposal_date",
    ),
    step(
        "ALTER TABLE sealed ADD COLUMN disposal_note TEXT NULL",
        "ALTER TABLE sealed DROP COLUMN disposal_note",
    ),
]
