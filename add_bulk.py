import sqlite3
import os
import shutil

def add_bulk_sales_table(db_path):
    """
    Adds the bulk_sales and bulk_counter tables to the database if they don't exist.
    """

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='bulk_counter'
        """)
        bulk_counter_exists = cursor.fetchone() is not None

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='bulk_sales'
        """)
        bulk_sales_exists = cursor.fetchone() is not None

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='bulk_items'
        """)
        bulk_items_exists = cursor.fetchone() is not None

        if bulk_counter_exists:
            print("Bulk tables already exist, skipping addition.")
        else:            
            print("Adding bulk_sales and bulk_counter tables...")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bulk_counter (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    counter_name TEXT UNIQUE NOT NULL,
                    counter INTEGER DEFAULT 0
                )
            """)
            print("Created bulk_counter table.")
        cursor.execute("""
            INSERT OR IGNORE INTO bulk_counter (counter_name, counter)
            VALUES ('bulk', 0)
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO bulk_counter (counter_name, counter)
            VALUES ('holo', 0)
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO bulk_counter (counter_name, counter)
            VALUES ('ex', 0)
        """)
        
        if not bulk_sales_exists:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bulk_sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sale_id INTEGER NOT NULL,
                    item_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    total_price REAL NOT NULL,
                    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE
                )
            """)
            print("Created bulk_sales table.")
            cursor.execute("""
                CREATE INDEX idx_bulk_sales_sale_id ON bulk_sales(sale_id)
            """)
            print("Created index on bulk_sales.sale_id.")
        else:
            print("bulk_sales table already exists, skipping its addition.")

        if not bulk_items_exists:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bulk_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auction_id INTEGER NOT NULL,
                    item_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    total_price REAL NOT NULL,
                    FOREIGN KEY (auction_id) REFERENCES auctions (id),
                    UNIQUE(auction_id, item_type)
                )
            """)
            print("Created bulk_items table.")
            cursor.execute("""
                CREATE INDEX idx_bulk_items_auction_id ON bulk_items(auction_id)
            """)
            print("Created index on bulk_items.auction_id.")
        else:
            print("bulk_items table already exists, skipping its addition.")

        conn.commit()
        conn.close()
        return True
    
    except sqlite3.Error as e:
        print(f"SQLite error during bulk tables addition: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error during bulk tables addition: {e}")
        return False
    
if __name__ == "__main__":
    db_path = "trade_tracker.db"  # Update with your actual database path
    if add_bulk_sales_table(db_path):
        print("Bulk tables added or already exist.")
    else:
        print("Failed to add bulk tables.")
    
