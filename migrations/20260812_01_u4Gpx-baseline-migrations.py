"""Mark the current schema as the Yoyo migration baseline."""

from yoyo import step


__depends__ = {}

steps = [
    step("SELECT 1"),
]
