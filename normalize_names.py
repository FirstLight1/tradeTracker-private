import sqlite3
import unicodedata

def normalize(s: str | None) -> str | None:
    if s is None:
        return None
    # NFD decomposes é → e + combining accent, then encode/decode drops the accent
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").upper()

def normalize_names(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT id, card_name FROM cards")
    for name in cursor.fetchall():
        norm_name = normalize(name[1])
        id = name[0]
        cursor.execute("UPDATE cards SET normalized_name = ? WHERE id = ?", (norm_name, id))
    conn.commit()

if __name__ == "__main__":
    conn = sqlite3.connect("instance/tradeTracker.sqlite")
    normalize_names(conn)
    conn.close()

