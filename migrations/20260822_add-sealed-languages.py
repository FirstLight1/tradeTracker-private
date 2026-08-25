"""
Language for sealed
"""

from yoyo import step

__depends__ = {}

steps = [
    step("ALTER TABLE sealed ADD language TEXT DEFAULT 'en' ",
         "ALTER TABLE sealed DROP COLUMN language")
]
