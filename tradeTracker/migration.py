import sqlite3
import os
import sys
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
                    FOREIGN KEY (auction_id) REFERENCES auctions(id),
                    FOREIGN KEY (sale_id) REFERENCES sales(id)
    );
 
            """)
        else:
            print("Barter table already exists, skipping migration")
    except sqlite3.Error as e:
        print(f"Error checking for sales table: {e}")

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
                    FOREIGN KEY (auction_id) REFERENCES auctions(id)
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



