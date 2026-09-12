#!/usr/bin/env python3
"""Remove the star symbol from card names in a SQLite database.

Usage:
    python scripts/remove_star_from_card_names.py --db instance/tradeTracker.sqlite
    python scripts/remove_star_from_card_names.py --db instance/tradeTracker.sqlite --apply
"""

import argparse
import sqlite3
from pathlib import Path


STAR = "\u2b50"


def clean_name(name: str) -> str:
    return name.replace(STAR, "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove the star symbol from cards.card_name (dry-run by default)."
    )
    parser.add_argument("--db", required=True, type=Path, help="Path to the SQLite database")
    parser.add_argument("--apply", action="store_true", help="Apply the displayed changes")
    args = parser.parse_args()

    if not args.db.is_file():
        parser.error(f"database file does not exist: {args.db}")

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== remove_star_from_card_names.py - {mode} ===")
    print(f"Database: {args.db}")

    with sqlite3.connect(args.db) as conn:
        rows = conn.execute(
            "SELECT id, card_name FROM cards WHERE instr(card_name, ?) > 0 ORDER BY id",
            (STAR,),
        ).fetchall()
        updates = [(clean_name(name), row_id) for row_id, name in rows]

        for (row_id, old_name), (new_name, _) in zip(rows, updates):
            print(f"  cards id={row_id}: {old_name!r} -> {new_name!r}")

        if args.apply and updates:
            conn.executemany(
                "UPDATE cards SET card_name = ? WHERE id = ?",
                updates,
            )

    if args.apply:
        print(f"Updated {len(updates)} card(s).")
    else:
        print(f"Dry-run complete: {len(updates)} card(s) would be updated.")
        if updates:
            print("Run again with --apply to execute.")


if __name__ == "__main__":
    main()
