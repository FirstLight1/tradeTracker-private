"""
Language for sealed
"""

from yoyo import step

__depends__ = {'20260812_01_u4Gpx-baseline-migrations'}


def add_language(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info(sealed)')}
    if columns and 'language' not in columns:
        connection.execute("ALTER TABLE sealed ADD language TEXT DEFAULT 'en'")


def remove_language(connection):
    columns = {row[1] for row in connection.execute('PRAGMA table_info(sealed)')}
    if 'language' in columns:
        connection.execute('ALTER TABLE sealed DROP COLUMN language')


steps = [
    step(add_language, remove_language)
]
