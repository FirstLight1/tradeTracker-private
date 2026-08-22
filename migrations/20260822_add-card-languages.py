"""
Add card_languages collumn to cards table
"""

from yoyo import step

__depends__ = {'20260812_01_u4Gpx-baseline-migrations'}

steps = [
    step("ALTER TABLE cards ADD language TEXT DEFAULT 'en'",
         "ALTER TABLE cards DROP COLUMN language")
]
