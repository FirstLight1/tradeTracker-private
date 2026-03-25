import sqlite3
import click
import logging
from flask import current_app, g
import time

logger = logging.getLogger(__name__)
SLOW_QUERY_THRESHOLD_MS = 200

class LoggingCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, query, params=None):
        start = time.perf_counter()
        try:
            self._cursor.execute(query, params or ())
            duration_ms = (time.perf_counter() - start) * 1000

            if duration_ms > SLOW_QUERY_THRESHOLD_MS:
                logger.warning(
                        "Slow query | %.2fms | %s | params: %s",
                        duration_ms, query, params,
                        )
            else:
                pass
            # logger.debug(
                    #     "Query OK | %.2fms | %s", duration_ms, query
                    # )

            return self   # ← important: lets cursor.lastrowid work

        except Exception:
            logger.exception(
                    "Query failed | %s | params: %s", query, params
                    )
            raise

    def executemany(self, query, params_list):
        start = time.perf_counter()
        try:
            self._cursor.executemany(query, params_list)
            duration_ms = (time.perf_counter() - start) * 1000

            if duration_ms > SLOW_QUERY_THRESHOLD_MS:
                logger.warning(
                        "Slow executemany | %.2fms | %s | %d rows",
                        duration_ms, query, len(params_list),
                        )
            else:
                logger.debug(
                        "Executemany OK | %.2fms | %s | %d rows",
                        duration_ms, query, len(params_list),
                        )

            return self

        except Exception:
            logger.exception(
                    "Executemany failed | %s | %d rows",
                    query, len(params_list)
                    )
            raise

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class LoggingConnection:
    def __init__(self, connection):
        self._conn = connection

    def cursor(self):
        return LoggingCursor(self._conn.cursor())

    def execute(self, query, params=None):
        return LoggingCursor(self._conn.cursor()).execute(query, params)

    def commit(self):
        #logger.debug("Transaction committed")
        self._conn.commit()

    def rollback(self):
        logger.warning("Transaction rolled back")
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_db():
    if 'db' not in g:
        conn  = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        conn.row_factory = sqlite3.Row
        g.db = LoggingConnection(conn)
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_db():
    db = get_db()

    try:
        # Schema is included directly in the code to avoid file access issues
        schema = '''
DROP TABLE IF EXISTS info;
DROP TABLE IF EXISTS sale_items;
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS auctions;
DROP TABLE IF EXISTS cards;
DROP TABLE IF EXISTS collection;
DROP TABLE IF EXISTS bulk_counter;
DROP TABLE IF EXISTS bulk_sales;
DROP TABLE IF EXISTS bulk_items;
DROP TABLE IF EXISTS sealed;

CREATE TABLE auctions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_name TEXT,
    auction_price REAL,
    auction_profit REAL,
    payment_method TEXT,
    date_created TEXT
);

INSERT INTO auctions (auction_name, auction_profit) VALUES ('Singles', 0);

CREATE TABLE cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_id INTEGER NOT NULL,
    card_name TEXT NOT NULL,
    card_num TEXT,
    condition TEXT,
    card_price REAL,
    market_value REAL,
    FOREIGN KEY (auction_id) REFERENCES auctions (id)
);

CREATE INDEX idx_cards_card_name ON cards(card_name);
CREATE INDEX idx_cards_card_num ON cards(card_num);
CREATE INDEX idx_cards_auction_id ON cards(auction_id);

CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    sale_date TEXT NOT NULL,
    total_amount REAL,
    notes TEXT,
    shipping_info TEXT
);

CREATE INDEX idx_sales_invoice ON sales(invoice_number);
CREATE INDEX idx_sales_date ON sales(sale_date);

CREATE TABLE sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    card_id INTEGER NOT NULL,
    sell_price REAL NOT NULL,
    sold_cm INTEGER DEFAULT 0,
    sold INTEGER DEFAULT 0,
    profit REAL,
    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE,
    FOREIGN KEY (card_id) REFERENCES cards (id) ON DELETE CASCADE
);

CREATE INDEX idx_sale_items_sale_id ON sale_items(sale_id);
CREATE INDEX idx_sale_items_card_id ON sale_items(card_id);

CREATE TABLE bulk_counter(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    counter_name TEXT UNIQUE NOT NULL,
    counter INTEGER DEFAULT 0
);

INSERT INTO bulk_counter (counter_name, counter) VALUES ('bulk', 0);
INSERT INTO bulk_counter (counter_name, counter) VALUES ('holo', 0);
INSERT INTO bulk_counter (counter_name, counter) VALUES ('ex', 0);

CREATE TABLE bulk_items(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    FOREIGN KEY (auction_id) REFERENCES auctions (id),
    UNIQUE(auction_id, item_type)
);

CREATE INDEX idx_bulk_items_auction_id ON bulk_items(auction_id);
CREATE INDEX idx_bulk_items_item_type ON bulk_items(item_type);

CREATE TABLE bulk_sales(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE
    );

CREATE INDEX idx_bulk_sales_sale_id ON bulk_sales(sale_id);

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
    );

CREATE INDEX idx_sealed_name ON sealed(name);
CREATE INDEX idx_sealed_auction_id ON sealed(auction_id);

CREATE TABLE collection(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_name TEXT NOT NULL,
    card_num TEXT,
    condition TEXT,
    buy_price REAL,
    market_value REAL
);

CREATE TABLE barter(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_id INTEGER,
    sale_id INTEGER,
    FOREIGN KEY (auction_id) REFERENCES auctions(id),
    FOREIGN KEY (sale_id) REFERENCES sales(id)
    );
'''
        db.executescript(schema)
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
