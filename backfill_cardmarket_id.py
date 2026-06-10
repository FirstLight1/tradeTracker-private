"""
One-off backfill: populate cardMarketID on the cards or sealed table from a CSV.

This is NOT a startup migration. The CSV is not in the repo, and this should run
exactly once (per CSV) by hand on the server, after a DB backup. The schema column
already exists on both tables (see migration.py / db.py).

Usage (PowerShell, on the prod box, venv active):

    # 1. ALWAYS back up first -- SQLite is a single file, the copy is your rollback:
    Copy-Item $env:DATA_DIR\tradeTracker.sqlite $env:DATA_DIR\tradeTracker.sqlite.bak

    # 2. Dry run -- writes nothing, just reports what WOULD happen:
    python backfill_cardmarket_id.py --csv cards.csv --db $env:DATA_DIR\tradeTracker.sqlite

    # 3. If the numbers look right, commit:
    python backfill_cardmarket_id.py --csv cards.csv --db $env:DATA_DIR\tradeTracker.sqlite --commit

    # Sealed products are matched by name only -- pass --table sealed:
    python backfill_cardmarket_id.py --table sealed --csv sealed.csv --db ... --commit

Matching key depends on the table:
  - cards : card_name + card_num + condition (case/whitespace-insensitive).
            Condition values are normalized through CONSTANTS.CONDITION_DICT so a
            Cardmarket "NM" matches a stored "NEAR MINT".
  - sealed: name only (case/whitespace-insensitive). Sealed products have no
            card number or condition.

A key can match several DB rows (duplicate copies / re-imports). The CSV's
`quantity` column says how many to tag; we take that many of the most recently
added matching rows that don't already have a cardMarketID (highest id first),
stopping when we run out of rows or of quantity. Use --overwrite to also retag
rows that already have an ID.
"""

import argparse
import csv
import os
import sqlite3
import sys

# Reuse the project's condition mapping so CSV codes match stored values.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tradeTracker"))
import CONSTANTS  # noqa: E402

# --- CSV column names. Adjust these to match your file's header row. ---
COL_NAME = "name"
COL_NUM = "cn"
COL_SET = "setCode"
COL_CONDITION = "condition"
COL_CARDMARKET_ID = "cardmarketId"
COL_SEALED_NAME = "name"
COL_QUANTITY = "quantity"


def norm_text(value):
    """Trim + uppercase for case/whitespace-insensitive comparison."""
    return (value or "").strip().upper()


def norm_condition(value):
    """Map a Cardmarket code (NM, MT, ...) to its stored form, else just normalize."""
    raw = (value or "").strip()
    mapped = CONSTANTS.CONDITION_DICT.get(raw.upper())
    return norm_text(mapped if mapped is not None else raw)


def card_key(name, num, condition):
    return (norm_text(name), norm_text(num), norm_condition(condition))

def whole_number(set, num):
    return set + " " + num

# --- Per-table behaviour. Picked by --table. ----------------------------------
# Each spec knows which CSV columns it needs, how to read the matching rows out
# of the DB, and how to derive the same match key from a DB row vs. a CSV row.
# Both tables can have several rows sharing a match key; the CSV quantity says
# how many of the most-recently-added ones to tag.
TABLE_SPECS = {
    "cards": {
        # One DB row per physical copy -- match on name + number + condition.
        "required_cols": (COL_NAME, COL_NUM, COL_SET, COL_CONDITION, COL_CARDMARKET_ID, COL_QUANTITY),
        "db_select": "SELECT id, card_name, card_num, condition FROM cards",
        "db_key": lambda row: card_key(row[1], row[2], row[3]),
        # DB card_num is stored as "<expansion> <number>" (see actions.py),
        # so rebuild the same combined form from the CSV's setCode + number.
        "csv_key": lambda row: card_key(
            row[COL_NAME], whole_number(row[COL_SET], row[COL_NUM]), row[COL_CONDITION]
        ),
    },
    "sealed": {
        # Sealed products have no number/condition -- match on name alone.
        "required_cols": (COL_SEALED_NAME, COL_CARDMARKET_ID, COL_QUANTITY),
        "db_select": "SELECT id, name FROM sealed",
        "db_key": lambda row: (norm_text(row[1]),),
        "csv_key": lambda row: (norm_text(row[COL_SEALED_NAME]),),
    },
}


def build_index(conn, spec):
    """
    Map a match key -> list of row ids for the chosen table.
    A key may map to several ids (duplicate copies / re-imports).
    """
    index = {}
    for row in conn.execute(spec["db_select"]):
        index.setdefault(spec["db_key"](row), []).append(row[0])
    return index


def main():
    parser = argparse.ArgumentParser(description="Backfill cardMarketID from a CSV.")
    parser.add_argument("--table", choices=sorted(TABLE_SPECS), default="cards",
                        help="Which table to backfill (default: cards).")
    parser.add_argument("--csv", required=True, help="Path to the source CSV.")
    parser.add_argument("--db", required=True, help="Path to the SQLite DB file.")
    parser.add_argument("--commit", action="store_true",
                        help="Actually write changes. Without this it's a dry run.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Also overwrite rows that already have a cardMarketID.")
    args = parser.parse_args()

    spec = TABLE_SPECS[args.table]

    if not os.path.exists(args.db):
        sys.exit(f"DB not found: {args.db}")
    if not os.path.exists(args.csv):
        sys.exit(f"CSV not found: {args.csv}")

    conn = sqlite3.connect(args.db)
    try:
        index = build_index(conn, spec)

        # Which rows already have an ID, so we can skip unless --overwrite.
        already_set = {
            row[0] for row in conn.execute(
                f"SELECT id FROM {args.table} "
                "WHERE cardMarketID IS NOT NULL AND cardMarketID != ''"
            )
        }

        updates = []          # (cardMarketID, row_id)
        not_found = []        # csv row number
        quantity_mismatch = []  # (row number, csv_qty, db_row_count): wanted > rows
        skipped_existing = 0
        missing_id = 0

        with open(args.csv, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for missing in spec["required_cols"]:
                if missing not in reader.fieldnames:
                    sys.exit(
                        f"CSV is missing column '{missing}'. "
                        f"Found columns: {reader.fieldnames}. "
                        f"Edit the COL_* constants at the top of this script to match."
                    )

            for lineno, row in enumerate(reader, start=2):  # line 1 is the header
                cm_id = (row.get(COL_CARDMARKET_ID) or "").strip()
                if not cm_id:
                    missing_id += 1
                    continue

                key = spec["csv_key"](row)
                ids = index.get(key)
                if not ids:
                    not_found.append(lineno)
                    continue

                # Newest first -- id is autoincrement, so a higher id means a
                # more recently added row. We tag the most recent matches that
                # still need an ID (unless --overwrite, which ignores that).
                ordered = sorted(ids, reverse=True)
                if args.overwrite:
                    candidates = ordered
                else:
                    candidates = [cid for cid in ordered if cid not in already_set]

                # CSV quantity = how many copies to tag. Take that many of the
                # most recent matches, decreasing until we run out of rows or of
                # quantity. If the CSV wants more than the DB actually has, tag
                # everything available and flag the shortfall.
                try:
                    want = int((row.get(COL_QUANTITY) or "").strip())
                except ValueError:
                    want = 1
                if want < 1:
                    want = 1
                if want > len(ids):
                    quantity_mismatch.append((lineno, want, len(ids)))

                target_ids = candidates[:want]
                if not target_ids:
                    # Every match already has an ID (and no --overwrite).
                    skipped_existing += 1
                    continue
                for cid in target_ids:
                    updates.append((cm_id, cid))

        print("--- Backfill summary ---")
        print(f"  matched & to update : {len(updates)}")
        print(f"  skipped (has ID)    : {skipped_existing}  (use --overwrite to replace)")
        print(f"  CSV rows w/o an ID  : {missing_id}")
        print(f"  not found in DB     : {len(not_found)}")
        print(f"  qty > rows in DB    : {len(quantity_mismatch)}")

        if not_found:
            preview = ", ".join(str(n) for n in not_found[:20])
            print(f"    not-found CSV lines: {preview}{' ...' if len(not_found) > 20 else ''}")
        if quantity_mismatch:
            for lineno, want, db_count in quantity_mismatch[:20]:
                print(f"    line {lineno}: CSV wants {want} but DB has {db_count} matching row(s)")

        if not args.commit:
            print("\nDRY RUN -- nothing written. Re-run with --commit to apply.")
            return

        with conn:  # single transaction; rolls back on any error
            conn.executemany(
                f"UPDATE {args.table} SET cardMarketID = ? WHERE id = ?", updates
            )
        print(f"\nCOMMITTED: {len(updates)} rows updated.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
