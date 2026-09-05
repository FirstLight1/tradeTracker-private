#!/usr/bin/env python3
"""
Standalone migration script to normalize date formats in
auctions.date_created and sealed.date to canonical ISO 8601
(YYYY-MM-DDTHH:MM:SS[.fractional]Z).

Usage:
    python3 scripts/normalize_dates.py --db instance/tradeTracker.sqlite            # dry-run
    python3 scripts/normalize_dates.py --db instance/tradeTracker.sqlite --apply     # apply
"""

import argparse
import datetime
import re
import sqlite3
import sys

CANONICAL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
DD_MM_YYYY_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")
DD_MM_YYYY_HMS_RE = re.compile(r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}$")
YYYY_MM_DD_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_OBJ_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}\.\d+)\+00:00$")


def normalize_auction_date(value):
    """Return (normalized_value, action_label) or (None, 'skip')."""
    if value is None:
        return None, "skip"

    if CANONICAL_RE.match(value):
        return value, "skip"

    if "+00:00Z" in value:
        return value.replace("+00:00", ""), "strip_double_tz"

    if DD_MM_YYYY_RE.match(value):
        dt = datetime.datetime.strptime(value, "%d-%m-%Y")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "dd_mm_yyyy"

    if YYYY_MM_DD_RE.match(value):
        return value + "T00:00:00Z", "pad_date_only"

    return None, "unknown"


def normalize_sealed_date(value):
    """Return (normalized_value, action_label) or (None, 'skip')."""
    if value is None:
        return None, "skip"

    if value == "-2003":
        return None, "null_corrupted"

    if CANONICAL_RE.match(value):
        return value, "skip"

    if DD_MM_YYYY_HMS_RE.match(value):
        dt = datetime.datetime.strptime(value, "%d-%m-%Y %H:%M:%S")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ"), "dd_mm_yyyy_hms"

    if YYYY_MM_DD_RE.match(value):
        return value + "T00:00:00Z", "pad_date_only"

    m = DATETIME_OBJ_RE.match(value)
    if m:
        return f"{m.group(1)}T{m.group(2)}Z", "datetime_obj_string"

    return None, "unknown"


def migrate_table(conn, table, column, normalizer, apply):
    rows = conn.execute(f"SELECT id, {column} FROM {table}").fetchall()

    counts = {}
    updates = []
    skipped = []
    unknowns = []

    for row_id, value in rows:
        normalized, action = normalizer(value)
        counts[action] = counts.get(action, 0) + 1

        if action == "skip":
            continue
        elif action == "unknown":
            unknowns.append((row_id, value))
            print(f"  WARNING: skipping {table} id={row_id} — unrecognized format: {value!r}")
            continue

        old_repr = "NULL" if value is None else repr(value)
        new_repr = "NULL" if normalized is None else repr(normalized)
        print(f"  {table} id={row_id}: {old_repr} -> {new_repr}  ({action})")

        if normalized is None:
            updates.append((None, row_id))
        else:
            updates.append((normalized, row_id))

    if apply and updates:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.executemany(
                f"UPDATE {table} SET {column} = ? WHERE id = ?",
                updates,
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    return counts, len(updates), len(unknowns)


def main():
    parser = argparse.ArgumentParser(
        description="Normalize date formats in auctions.date_created and sealed.date to ISO 8601."
    )
    parser.add_argument("--db", required=True, help="Path to the SQLite database file")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== normalize_dates.py — {mode} ===")
    print(f"Database: {args.db}")
    print()

    conn = sqlite3.connect(args.db)

    print(f"--- auctions.date_created ---")
    a_counts, a_updates, a_unknowns = migrate_table(
        conn, "auctions", "date_created", normalize_auction_date, args.apply
    )
    print(f"  Summary: {a_counts}")
    print(f"  Updates to apply: {a_updates}")
    print(f"  Unknown (skipped): {a_unknowns}")
    print()

    print(f"--- sealed.date ---")
    s_counts, s_updates, s_unknowns = migrate_table(
        conn, "sealed", "date", normalize_sealed_date, args.apply
    )
    print(f"  Summary: {s_counts}")
    print(f"  Updates to apply: {s_updates}")
    print(f"  Unknown (skipped): {s_unknowns}")
    print()

    conn.close()

    total_updates = a_updates + s_updates
    total_unknowns = a_unknowns + s_unknowns

    if args.apply:
        print(f"Done — {total_updates} rows updated, {total_unknowns} skipped (unknown format).")
    else:
        print(
            f"Dry-run complete — {total_updates} rows would be updated, {total_unknowns} skipped (unknown format)."
        )
        print("Run with --apply to execute.")

    if total_unknowns > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
