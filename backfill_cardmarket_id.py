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

    # Or do both tables in one go (cards then sealed) from a single CSV:
    python backfill_cardmarket_id.py --table both --csv cards.csv --db ... --commit

Matching key depends on the table:
  - cards : card_name + card_num (case/whitespace-insensitive). The Cardmarket
            product export is a catalogue with no per-copy condition, and
            cardMarketID is a per-product id shared across every condition, so
            condition is intentionally NOT part of the key.
  - sealed: name only (case/whitespace-insensitive). Sealed products have no
            card number or condition.

Every DB row whose key matches a CSV row gets that row's cardMarketID. A key can
match several DB rows (different conditions / duplicate copies / re-imports);
all of them are tagged. Rows that already have a cardMarketID are left alone
unless --overwrite is given.
"""

import argparse
import csv
import os
import sqlite3
import sys

# --- CSV column names. Match the Cardmarket product export header row. ---
COL_NAME = "name"
COL_NUM = "collectorNumber"
COL_SET = "expansionCode"
COL_CARDMARKET_ID = "cardmarketId"
COL_SEALED_NAME = "name"


def norm_text(value):
    """Trim + uppercase for case/whitespace-insensitive comparison."""
    return (value or "").strip().upper()


def card_key(name, num):
    return (norm_text(name), norm_text(num))


def whole_number(set, num):
    # Mirror how card_num is stored on import (actions.py): "<setCode> <number>",
    # but just the set when there is no collector number.
    set, num = (set or "").strip(), (num or "").strip()
    return f"{set} {num}".strip() if num else set


# --- Per-table behaviour. Picked by --table. ----------------------------------
# Each spec knows which CSV columns it needs, how to read the matching rows out
# of the DB, and how to derive the same match key from a DB row vs. a CSV row.
# Both tables can have several rows sharing a match key; every one of them is
# tagged with the CSV row's cardMarketID.
TABLE_SPECS = {
    "cards": {
        # One DB row per physical copy -- the catalogue export has no condition,
        # so match on name + number and tag every condition of the card.
        "required_cols": (COL_NAME, COL_NUM, COL_SET, COL_CARDMARKET_ID),
        "db_select": "SELECT id, card_name, card_num FROM cards",
        "db_key": lambda row: card_key(row[1], row[2]),
        # DB card_num is stored as "<setCode> <number>" (see actions.py),
        # so rebuild the same combined form from the CSV's expansionCode + number.
        "csv_key": lambda row: card_key(row[COL_NAME], whole_number(row[COL_SET], row[COL_NUM])),
    },
    "sealed": {
        # Sealed products have no number/condition -- match on name alone.
        "required_cols": (COL_SEALED_NAME, COL_CARDMARKET_ID),
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


def backfill_table(conn, table, csv_path, commit, overwrite):
    """Backfill one table. Prints a summary; writes only when commit is True."""
    spec = TABLE_SPECS[table]

    index = build_index(conn, spec)

    # Which rows already have an ID, so we can skip unless --overwrite.
    already_set = {
        row[0]
        for row in conn.execute(
            f"SELECT id FROM {table} WHERE cardMarketID IS NOT NULL AND cardMarketID != ''"
        )
    }

    updates = {}  # row_id -> cardMarketID (dict de-dups shared rows)
    not_found = []  # csv row number
    skipped_existing = 0
    missing_id = 0

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
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

            # Tag every matching row. Rows that already have an ID are left
            # alone unless --overwrite is set.
            tagged_any = False
            for cid in ids:
                if not overwrite and cid in already_set:
                    continue
                updates[cid] = cm_id
                tagged_any = True
            if not tagged_any:
                # Every match already has an ID (and no --overwrite).
                skipped_existing += 1

    print(f"--- Backfill summary [{table}] ---")
    print(f"  matched & to update : {len(updates)}")
    print(f"  CSV rows all set    : {skipped_existing}  (use --overwrite to replace)")
    print(f"  CSV rows w/o an ID  : {missing_id}")
    print(f"  not found in DB     : {len(not_found)}")

    if not_found:
        preview = ", ".join(str(n) for n in not_found[:20])
        print(f"    not-found CSV lines: {preview}{' ...' if len(not_found) > 20 else ''}")

    if not commit:
        print(f"  DRY RUN [{table}] -- nothing written. Re-run with --commit to apply.")
        return

    with conn:  # single transaction; rolls back on any error
        conn.executemany(
            f"UPDATE {table} SET cardMarketID = ? WHERE id = ?",
            [(cm_id, cid) for cid, cm_id in updates.items()],
        )
    print(f"  COMMITTED [{table}]: {len(updates)} rows updated.")


def main():
    parser = argparse.ArgumentParser(description="Backfill cardMarketID from a CSV.")
    parser.add_argument(
        "--table",
        choices=[*sorted(TABLE_SPECS), "both"],
        default="cards",
        help="Which table to backfill: cards, sealed, or both (default: cards).",
    )
    parser.add_argument("--csv", required=True, help="Path to the source CSV.")
    parser.add_argument("--db", required=True, help="Path to the SQLite DB file.")
    parser.add_argument(
        "--commit", action="store_true", help="Actually write changes. Without this it's a dry run."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Also overwrite rows that already have a cardMarketID.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"DB not found: {args.db}")
    if not os.path.exists(args.csv):
        sys.exit(f"CSV not found: {args.csv}")

    # "both" runs cards then sealed; each table is its own transaction.
    tables = sorted(TABLE_SPECS) if args.table == "both" else [args.table]

    conn = sqlite3.connect(args.db)
    try:
        for i, table in enumerate(tables):
            if i:
                print()
            backfill_table(conn, table, args.csv, args.commit, args.overwrite)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
