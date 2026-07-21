import sqlite3
import os
import re
import sys
import unicodedata
# Import the sales history migration logic
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)
from migrate_to_sales_history import migrate_to_sales_history
from add_bulk import add_bulk_sales_table

def migrate_database(db_path):
    """
    Applies database migrations.
    """
    if not os.path.exists(db_path):
        print("Database not found, skipping migration.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Migration 1: Add 'sold_date' to 'cards' table
        _add_sold_date_to_cards(cursor)
        
        # Migration 2: Add 'sold' column to 'sale_items' table
        _add_sold_to_sale_items(cursor)

        #Mingration 3: Add 'payment_method' to 'auctions' table
        add_payment_method_to_auctions(cursor)

        
        conn.commit()
        conn.close()
        
        # Migration 4: Migrate to sales history structure (checks if sales table exists)
        _migrate_to_sales_history_wrapper(db_path)
        # Migration 5: Add bulk sales and counter tables if they don't exist
        add_bulk_sales_table(db_path)
        # Migration 6: Add sealed products table
        addSealedProductsTable(db_path)
        # Migration 7: Add shipping info collumn to sales table
        addShippingInfoColumn(db_path)

        addBarterTable(db_path)
        # Migration 8: Ensure barter foreign keys are configured with ON DELETE CASCADE
        ensureBarterOnDeleteCascade(db_path)
        # Migration 9: Ensure cards/bulk_items/sealed cascade when their auction is deleted
        ensureAuctionsOnDeleteCascade(db_path)

        # Migration 10: Repair any FKs left dangling by a prior buggy run of
        # the rebuild migrations (SQLite >= 3.25 silently rewrote child-table
        # FK clauses to point at *_old during ALTER TABLE RENAME).
        repairDanglingForeignKeys(db_path)

        # Migration 11: Add quantity to sealed table
        addQuantityToSealedTable(db_path)

        # Migration 12: Add cardMarketID to cards table
        addCardMarketIDToCardsTable(db_path)

        # Migration 13: Add idOrder to sales table
        addIdOrderToSalesTable(db_path)

        addNormalizedNameToCardsTable(db_path)
        addNormalizedNameToSealedTable(db_path)
        
        addOpenedFlagToSealedTable(db_path)

        createSalesCorrectionTable(db_path)
        addUniqueIndexOnSalesCorrectionRecord(db_path)

        createExternalTable(db_path)
        print("Database migration check complete.")
    except sqlite3.Error as e:
        print(f"Database migration failed: {e}")

def _add_sold_date_to_cards(cursor):
    """
    Adds the 'sold_date' column to the 'cards' table if it doesn't exist.
    """
    try:
        # Check if the column already exists
        cursor.execute("PRAGMA table_info(cards)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'sold_date' not in columns:
            print("Applying migration: Adding 'sold_date' to 'cards' table...")
            cursor.execute("ALTER TABLE cards ADD COLUMN sold_date TEXT")
            print("'sold_date' column added successfully.")
        else:
            print("'sold_date' column already exists in 'cards' table.")
    except sqlite3.Error as e:
        # This can happen if the table doesn't exist yet, which is fine.
        if "no such table: cards" in str(e):
            print("'cards' table not found, skipping 'sold_date' column migration.")
        else:
            raise e

def _add_sold_to_sale_items(cursor):
    """
    Adds the 'sold' column to the 'sale_items' table if it doesn't exist.
    """
    try:
        # Check if the column already exists
        cursor.execute("PRAGMA table_info(sale_items)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'sold' not in columns:
            print("Applying migration: Adding 'sold' to 'sale_items' table...")
            cursor.execute("ALTER TABLE sale_items ADD COLUMN sold INTEGER DEFAULT 0")
            print("'sold' column added successfully.")
        else:
            print("'sold' column already exists in 'sale_items' table.")
    except sqlite3.Error as e:
        # This can happen if the table doesn't exist yet, which is fine.
        if "no such table: sale_items" in str(e):
            print("'sale_items' table not found, skipping 'sold' column migration.")
        else:
            raise e
        
def add_payment_method_to_auctions(cursor):
    """
    Adds the 'payment_method' column to the 'auctions' table if it doesn't exist.
    """
    try:
        # Check if the column already exists
        cursor.execute("PRAGMA table_info(auctions)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'payment_method' not in columns:
            print("Applying migration: Adding 'payment_method' to 'auctions' table...")
            cursor.execute("ALTER TABLE auctions ADD COLUMN payment_method TEXT")
            print("'payment_method' column added successfully.")
        else:
            print("'payment_method' column already exists in 'auctions' table.")
    except sqlite3.Error as e:
        # This can happen if the table doesn't exist yet, which is fine.
        if "no such table: auctions" in str(e):
            print("'auctions' table not found, skipping 'payment_method' column migration.")
        else:
            raise e

def _migrate_to_sales_history_wrapper(db_path):
    """
    Wrapper to check if sales table exists and run migration if needed.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if sales table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='sales'
        """)
        sales_table_exists = cursor.fetchone() is not None
        
        conn.close()
        
        if not sales_table_exists:
            print("Sales table not found, running sales history migration...")
            migrate_to_sales_history(db_path)
        else:
            print("Sales table already exists, skipping sales history migration.")
            
    except sqlite3.Error as e:
        print(f"Error checking for sales table: {e}")

def addBarterTable(db_path):
    """
    Check if barter table exists and if not migrate
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='barter'")
        barterTableExists = cursor.fetchone() is not None


        if not barterTableExists:
            print("Barter table not found, running migration...")
            cursor.execute("""
                CREATE TABLE barter(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auction_id INTEGER,
                    sale_id INTEGER,
                    FOREIGN KEY (auction_id) REFERENCES auctions(id) ON DELETE CASCADE,
                    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE 
    );
 
            """)
            conn.commit()
        else:
            print("Barter table already exists, skipping migration")
    except sqlite3.Error as e:
        print(f"Error checking for sales table: {e}")
    finally:
        if conn:
            conn.close()


def ensureBarterOnDeleteCascade(db_path):
    """
    Ensures barter foreign keys use ON DELETE CASCADE.
    Recreates the table if old constraints are missing.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='barter'")
        barterTableExists = cursor.fetchone() is not None

        if not barterTableExists:
            print("'barter' table not found, skipping cascade migration.")
            return

        cursor.execute("PRAGMA foreign_key_list(barter)")
        fkRows = cursor.fetchall()

        onDeleteByColumn = {}
        for fk in fkRows:
            fromColumn = fk[3]
            onDelete = (fk[6] or "").upper()
            onDeleteByColumn[fromColumn] = onDelete

        auctionCascade = onDeleteByColumn.get("auction_id") == "CASCADE"
        saleCascade = onDeleteByColumn.get("sale_id") == "CASCADE"

        if auctionCascade and saleCascade:
            print("'barter' table already has ON DELETE CASCADE constraints.")
            return

        print("Applying migration: Recreating 'barter' table with ON DELETE CASCADE...")

        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute("PRAGMA legacy_alter_table = ON")
        cursor.execute("ALTER TABLE barter RENAME TO barter_old")
        cursor.execute("""
            CREATE TABLE barter(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auction_id INTEGER,
                sale_id INTEGER,
                FOREIGN KEY (auction_id) REFERENCES auctions(id) ON DELETE CASCADE,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            INSERT INTO barter (id, auction_id, sale_id)
            SELECT id, auction_id, sale_id FROM barter_old
        """)
        cursor.execute("DROP TABLE barter_old")
        conn.commit()
        cursor.execute("PRAGMA legacy_alter_table = OFF")
        cursor.execute("PRAGMA foreign_keys = ON")

        print("'barter' table recreated successfully with ON DELETE CASCADE.")
    except sqlite3.Error as e:
        print(f"Error ensuring 'barter' ON DELETE CASCADE constraints: {e}")
    finally:
        if conn:
            conn.close()

def _recoverStrandedOldTable(cursor, table):
    """
    If a prior un-transactioned rebuild of `table` crashed, the database may
    contain `<table>_old` (or both `<table>` and `<table>_old`). Restore a
    consistent state so the rebuild path can re-run safely.
    """
    oldName = f"{table}_old"
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (oldName,),
    )
    if cursor.fetchone() is None:
        return

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    mainExists = cursor.fetchone() is not None

    if not mainExists:
        print(f"Recovering '{table}': renaming stranded '{oldName}' back (prior run crashed mid-rebuild).")
        cursor.execute(f"ALTER TABLE {oldName} RENAME TO {table}")
        return

    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    newCount = cursor.fetchone()[0]
    cursor.execute(f"SELECT COUNT(*) FROM {oldName}")
    oldCount = cursor.fetchone()[0]

    if newCount == 0 and oldCount > 0:
        print(f"Recovering '{table}': new table is empty ({newCount}), restoring from '{oldName}' ({oldCount} rows).")
        cursor.execute(f"DROP TABLE {table}")
        cursor.execute(f"ALTER TABLE {oldName} RENAME TO {table}")
    elif newCount >= oldCount:
        print(f"'{oldName}' looks like leftover residue (new={newCount}, old={oldCount}); dropping it.")
        cursor.execute(f"DROP TABLE {oldName}")
    else:
        print(
            f"WARNING: both '{table}' ({newCount} rows) and '{oldName}' ({oldCount} rows) "
            f"contain data — manual inspection required, leaving as-is."
        )


def ensureAuctionsOnDeleteCascade(db_path):
    """
    Ensures the auction_id foreign keys on cards, bulk_items, and sealed
    use ON DELETE CASCADE. Each table is recreated only if its existing
    constraint is not already CASCADE. Indexes are preserved.
    """
    targets = [
        (
            "cards",
            """
                CREATE TABLE cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auction_id INTEGER NOT NULL,
                    card_name TEXT NOT NULL,
                    card_num TEXT,
                    condition TEXT,
                    card_price REAL,
                    market_value REAL,
                    sold_date TEXT,
                    FOREIGN KEY (auction_id) REFERENCES auctions (id) ON DELETE CASCADE
                )
            """,
        ),
        (
            "bulk_items",
            """
                CREATE TABLE bulk_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auction_id INTEGER NOT NULL,
                    item_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    total_price REAL NOT NULL,
                    FOREIGN KEY (auction_id) REFERENCES auctions (id) ON DELETE CASCADE,
                    UNIQUE(auction_id, item_type)
                )
            """,
        ),
        (
            "sealed",
            """
                CREATE TABLE sealed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL,
                    market_value REAL,
                    date TEXT,
                    sale_id INTEGER,
                    auction_id INTEGER,
                    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE,
                    FOREIGN KEY (auction_id) REFERENCES auctions(id) ON DELETE CASCADE
                )
            """,
        ),
    ]

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        # Autocommit mode so we control BEGIN/COMMIT/ROLLBACK explicitly.
        conn.isolation_level = None
        cursor = conn.cursor()

        # Recover any *_old tables stranded by a prior crashed run before
        # this hardening landed. Done first so the rebuild below sees a
        # consistent starting state.
        for table, _ in targets:
            _recoverStrandedOldTable(cursor, table)

        for table, newCreateSql in targets:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            if cursor.fetchone() is None:
                print(f"'{table}' table not found, skipping auctions cascade migration.")
                continue

            cursor.execute(f"PRAGMA foreign_key_list({table})")
            fkRows = cursor.fetchall()
            onDeleteByColumn = {fk[3]: (fk[6] or "").upper() for fk in fkRows}

            if onDeleteByColumn.get("auction_id") == "CASCADE":
                print(f"'{table}' already has ON DELETE CASCADE on auction_id.")
                continue

            print(f"Applying migration: Recreating '{table}' with ON DELETE CASCADE on auction_id...")

            cursor.execute(f"PRAGMA table_info({table})")
            existingColumns = [col[1] for col in cursor.fetchall()]

            cursor.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
                (table,),
            )
            indexSqls = [row[0] for row in cursor.fetchall()]

            # foreign_keys can only be toggled outside a transaction.
            # legacy_alter_table stops SQLite >= 3.25 from rewriting FK
            # references in OTHER tables when we RENAME below — without it,
            # sale_items' FK to cards silently becomes a FK to cards_old and
            # is left dangling once cards_old is dropped.
            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("PRAGMA legacy_alter_table = ON")
            try:
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
                cursor.execute(newCreateSql)

                cursor.execute(f"PRAGMA table_info({table})")
                newColumns = [col[1] for col in cursor.fetchall()]
                sharedColumns = [c for c in existingColumns if c in newColumns]
                colList = ", ".join(sharedColumns)
                cursor.execute(
                    f"INSERT INTO {table} ({colList}) SELECT {colList} FROM {table}_old"
                )
                cursor.execute(f"DROP TABLE {table}_old")

                for idxSql in indexSqls:
                    cursor.execute(idxSql)

                cursor.execute("COMMIT")
            except Exception:
                try:
                    cursor.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                cursor.execute("PRAGMA legacy_alter_table = OFF")
                cursor.execute("PRAGMA foreign_keys = ON")

            print(f"'{table}' recreated successfully with ON DELETE CASCADE on auction_id.")
    except sqlite3.Error as e:
        print(f"Error ensuring auctions ON DELETE CASCADE constraints: {e}")
    finally:
        if conn:
            conn.close()


def addSealedProductsTable(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""SELECT name FROM sqlite_master WHERE type='table' AND name='sealed'
                   """)

        exist = cursor.fetchone() is not None
        
        if not exist:
            print("Applying migration: Creating 'sealed' table...")
            cursor.execute("""
                CREATE TABLE sealed(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL,
                    market_value REAL,
                    date TEXT,
                    sale_id INTEGER,
                    auction_id INTEGER,
                    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE,
                    FOREIGN KEY (auction_id) REFERENCES auctions(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX idx_sealed_name ON sealed(name)")
            cursor.execute("CREATE INDEX idx_auction_id ON sealed(auction_id)")
            conn.commit()
            print("'sealed' table created successfully.")
        else:
            print("'sealed' table already exists.")
            
        conn.close()

    except sqlite3.Error as e:
        print(f"Error checking for table: {e}")


def addShippingInfoColumn(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if the column already exists
        cursor.execute("PRAGMA table_info(sales)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'shipping_info' not in columns:
            print("Applying migration: Adding 'shipping_info' to 'sales' table...")
            cursor.execute("ALTER TABLE sales ADD COLUMN shipping_info TEXT")
            print("'shipping_info' column added successfully.")
        else:
            print("'shipping_info' column already exists in 'sales' table.")
    except sqlite3.Error as e:
        # This can happen if the table doesn't exist yet, which is fine.
        if "no such table: sales" in str(e):
            print("'sales' table not found, skipping 'shipping_info' column migration.")
        else:
            raise e


def addIdOrderToSalesTable(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if the column already exists
        cursor.execute("PRAGMA table_info(sales)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'idOrder' not in columns:
            print("Applying migration: Adding 'idOrder' to 'sales' table...")
            cursor.execute("ALTER TABLE sales ADD COLUMN idOrder TEXT")
            print("'idOrder' column added successfully.")
        else:
            print("'idOrder' column already exists in 'sales' table.")
    except sqlite3.Error as e:
        # This can happen if the table doesn't exist yet, which is fine.
        if "no such table: sales" in str(e):
            print("'sales' table not found, skipping 'idOrder' column migration.")
        else:
            raise e


def repairDanglingForeignKeys(db_path):
    """
    Scan every user table for foreign-key clauses that reference a missing
    table, and rebuild the affected table with the FK retargeted to the
    obvious replacement (strip a trailing `_old` and use the base name if
    that table now exists).

    Why this exists: on SQLite >= 3.25, `ALTER TABLE X RENAME TO X_old`
    silently rewrites FK clauses in every child table to point at `X_old`.
    When the rebuild later drops `X_old`, those FK references become
    dangling, and the next write to a child table raises
    "no such table: main.X_old". This function self-heals that damage.

    Runs unconditionally: cheap on healthy databases (one PRAGMA per table,
    no rewrites), restorative on damaged ones.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.isolation_level = None  # autocommit; we own BEGIN/COMMIT
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        allTables = {row[0] for row in cursor.fetchall()}

        # tableName -> { brokenRefName: replacementName }
        repairPlan = {}
        for tableName in allTables:
            cursor.execute(f"PRAGMA foreign_key_list({tableName})")
            for fk in cursor.fetchall():
                referenced = fk[2]
                if referenced in allTables:
                    continue
                if referenced.endswith("_old") and referenced[:-4] in allTables:
                    repairPlan.setdefault(tableName, {})[referenced] = referenced[:-4]
                else:
                    print(
                        f"WARNING: '{tableName}' has a FK referencing missing "
                        f"table '{referenced}'; no obvious replacement — leaving as-is."
                    )

        if not repairPlan:
            print("FK repair: no dangling foreign-key references found.")
            return

        for tableName, rewrites in repairPlan.items():
            print(
                f"FK repair: '{tableName}' has dangling reference(s) "
                f"{rewrites}; rebuilding with corrected FK clause(s)..."
            )

            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (tableName,),
            )
            currentCreateSql = cursor.fetchone()[0]

            newCreateSql = currentCreateSql
            failed = False
            for brokenName, fixName in rewrites.items():
                # Match `REFERENCES <brokenName>` with optional quoting,
                # bounded so we don't touch substrings of other identifiers.
                pattern = re.compile(
                    r"(REFERENCES\s+)"
                    r"(?:\"" + re.escape(brokenName) + r"\""
                    r"|`" + re.escape(brokenName) + r"`"
                    r"|\[" + re.escape(brokenName) + r"\]"
                    r"|\b" + re.escape(brokenName) + r"\b)",
                    re.IGNORECASE,
                )
                newCreateSql, n = pattern.subn(
                    r"\g<1>" + fixName, newCreateSql
                )
                if n == 0:
                    print(
                        f"WARNING: could not locate 'REFERENCES {brokenName}' "
                        f"in '{tableName}' CREATE SQL — skipping this table, manual repair needed."
                    )
                    failed = True
                    break

            if failed or newCreateSql == currentCreateSql:
                continue

            cursor.execute(f"PRAGMA table_info({tableName})")
            existingColumns = [col[1] for col in cursor.fetchall()]

            cursor.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
                (tableName,),
            )
            indexSqls = [row[0] for row in cursor.fetchall()]

            tempName = f"{tableName}_fkrepair_old"

            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("PRAGMA legacy_alter_table = ON")
            try:
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute(f"ALTER TABLE {tableName} RENAME TO {tempName}")
                cursor.execute(newCreateSql)

                cursor.execute(f"PRAGMA table_info({tableName})")
                newColumns = [col[1] for col in cursor.fetchall()]
                sharedColumns = [c for c in existingColumns if c in newColumns]
                colList = ", ".join(sharedColumns)
                cursor.execute(
                    f"INSERT INTO {tableName} ({colList}) "
                    f"SELECT {colList} FROM {tempName}"
                )
                cursor.execute(f"DROP TABLE {tempName}")

                for idxSql in indexSqls:
                    cursor.execute(idxSql)

                cursor.execute("COMMIT")
                print(f"FK repair: '{tableName}' rebuilt successfully.")
            except Exception:
                try:
                    cursor.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                cursor.execute("PRAGMA legacy_alter_table = OFF")
                cursor.execute("PRAGMA foreign_keys = ON")
    except sqlite3.Error as e:
        print(f"Error repairing dangling foreign keys: {e}")
    finally:
        if conn:
            conn.close()

def addQuantityToSealedTable(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if the column already exists
        cursor.execute("PRAGMA table_info(sealed)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'quantity' not in columns:
            print("Applying migration: Adding 'quantity' to 'sealed' table...")
            cursor.execute("ALTER TABLE sealed ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1")
            print("'quantity' column added successfully.")
        else:
            print("'quantity' column already exists in 'sealed' table.")
    except sqlite3.Error as e:
        # This can happen if the table doesn't exist yet, which is fine.
        if "no such table: sealed" in str(e):
            print("'sealed' table not found, skipping 'quantity' column migration.")
        else:
            raise e

def addCardMarketIDToCardsTable(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(cards)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'cardMarketID' not in columns:
            print("Applying migration: Adding 'cardMarketID' to 'cards' table...")
            cursor.execute("ALTER TABLE cards ADD COLUMN cardMarketID TEXT NULL")
            print("'cardMarketID' column added successfully.")
        else:
            print("'cardMarketID' column already exists in 'cards' table.")

        cursor.execute("PRAGMA table_info(sealed)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'cardMarketID' not in columns:
            print("Applying migration: Adding 'cardMarketID' to 'cards' table...")
            cursor.execute("ALTER TABLE sealed ADD COLUMN cardMarketID TEXT NULL")
            print("'cardMarketID' column added successfully.")
        else:
            print("'cardMarketID' column already exists in 'sealed' table.")


    except sqlite3.Error as e:
        if "no such table: cards" in str(e):
            print("'sealed' table not found, skipping 'cardMarketID' column migration.")
        else:
            raise e


def addOpenedFlagToSealedTable(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Check if the column already exists
        cursor.execute("PRAGMA table_info(sealed)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'opened' not in columns:
            print("Applying migration: Adding 'opened' to 'sealed' table...")
            cursor.execute("ALTER TABLE sealed ADD COLUMN opened INTEGER DEFAULT 0")
            print("'opened' column added successfully.")
        else:
            print("'opened' column already exists in 'sealed' table.")
    except sqlite3.Error as e:
        # This can happen if the table doesn't exist yet, which is fine.
        if "no such table: sealed" in str(e):
            print("'sealed' table not found, skipping 'quantity' column migration.")
        else:
            raise e

def _normalize_name(s):
    # Keep in sync with actions.normalize — NFD decomposes é → e + combining accent,
    # then encode/decode drops the accent
    if s is None:
        return None
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").upper()

def addNormalizedNameToCardsTable(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(cards)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'normalized_name' not in columns:
            print("Applying migration: Adding 'normalized_name' to 'cards' table...")
            cursor.execute("ALTER TABLE cards ADD COLUMN normalized_name TEXT")
            print("'normalized_name' column added successfully.")
            cursor.execute("CREATE INDEX idx_cards_normalized_name ON cards(normalized_name)")
        else:
            print("'normalized_name' column already exists in 'cards' table.")

        # Backfill rows that predate the column (idempotent)
        cursor.execute("SELECT id, card_name FROM cards WHERE normalized_name IS NULL")
        rows = cursor.fetchall()
        if rows:
            print(f"Backfilling 'normalized_name' for {len(rows)} card rows...")
            for row_id, card_name in rows:
                cursor.execute("UPDATE cards SET normalized_name = ? WHERE id = ?", (_normalize_name(card_name), row_id))
            conn.commit()
            print("'normalized_name' backfill for 'cards' complete.")
        conn.close()

    except sqlite3.Error as e:
        if "no such table: cards" in str(e):
            print("'cards' table not found, skipping 'normalized_name' column migration.")
        else:
            raise e

def addNormalizedNameToSealedTable(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(sealed)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'normalized_name' not in columns:
            print("Applying migration: Adding 'normalized_name' to 'sealed' table...")
            cursor.execute("ALTER TABLE sealed ADD COLUMN normalized_name TEXT")
            print("'normalized_name' column added successfully.")
            cursor.execute("CREATE INDEX idx_sealed_normalized_name ON sealed(normalized_name)")
        else:
            print("'normalized_name' column already exists in 'sealed' table.")

        # Backfill rows that predate the column (idempotent)
        cursor.execute("SELECT id, name FROM sealed WHERE normalized_name IS NULL")
        rows = cursor.fetchall()
        if rows:
            print(f"Backfilling 'normalized_name' for {len(rows)} sealed rows...")
            for row_id, name in rows:
                cursor.execute("UPDATE sealed SET normalized_name = ? WHERE id = ?", (_normalize_name(name), row_id))
            conn.commit()
            print("'normalized_name' backfill for 'sealed' complete.")
        conn.close()

    except sqlite3.Error as e:
        if "no such table: sealed" in str(e):
            print("'sealed' table not found, skipping 'normalized_name' column migration.")
        else:
            raise e

def createSalesCorrectionTable(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_correction'")
        exist = cursor.fetchone() is not None


        if not exist:
            print("Correction table not found, running migration...")
            cursor.execute("""
                CREATE TABLE sales_correction(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER NOT NULL,
                    value_change REAL,
                    change_type TEXT NOT NULL,
                    record_number INTEGER NOT NULL,
                    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
                    );
            """)
            cursor.execute("CREATE INDEX idx_sales_correction_sale_id ON sales_correction(sale_id)")
            conn.commit()
        else:
            print("sales_correction table already exists, skipping migration")
    except sqlite3.Error as e:
        print(f"Error checking for sales table: {e}")
    finally:
        if conn:
            conn.close()

def addUniqueIndexOnSalesCorrectionRecord(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_sales_correction_record_unique'"
        )
        exists = cursor.fetchone() is not None

        if not exists:
            print("Adding UNIQUE index on sales_correction(record_number, change_type)...")
            cursor.execute(
                "CREATE UNIQUE INDEX idx_sales_correction_record_unique "
                "ON sales_correction(record_number, change_type)"
            )
            conn.commit()
            print("UNIQUE index created successfully.")
        else:
            print("UNIQUE index on sales_correction(record_number, change_type) already exists.")
    except sqlite3.Error as e:
        print(f"Error adding UNIQUE index on sales_correction: {e}")
    finally:
        if conn:
            conn.close()


def createExternalTable(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='external'")
        exist = cursor.fetchone() is not None


        if not exist:
            print("Correction table not found, running migration...")
            cursor.execute("""
                CREATE TABLE external(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cardmarketId TEXT NOT NULL UNIQUE,
                    card_name TEXT NOT NULL,
                    card_num TEXT,
                    expansion TEXT
                    );
            """)
            cursor.execute("CREATE INDEX idx_external_card_name ON external(card_name, card_num)")
            conn.commit()
        else:
            print("external table already exists, skipping migration")
    except sqlite3.Error as e:
        print(f"Error checking for external table: {e}")
    finally:
        if conn:
            conn.close()
