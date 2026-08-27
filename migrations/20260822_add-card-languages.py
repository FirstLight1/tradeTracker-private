"""
Add card_languages collumn to cards table
"""

from yoyo import step

__depends__ = {'20260812_01_u4Gpx-baseline-migrations'}


def add_language(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info(cards)')}
    if columns and 'language' not in columns:
        connection.execute("ALTER TABLE cards ADD language TEXT DEFAULT 'en'")


def remove_language(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info(cards)')}
    if 'language' in columns:
        connection.execute('ALTER TABLE cards DROP COLUMN language')


steps = [
    step(add_language, remove_language)
]
