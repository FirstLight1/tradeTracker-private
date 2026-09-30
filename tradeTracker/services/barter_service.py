

class BarterService:
    def __init__(self, db):
        self.db = db

    def get_unlinked_ids(self) -> list:
        ids = self.db.execute(
            'SELECT id, invoice_number FROM sales WHERE id NOT IN (SELECT sale_id FROM barter WHERE sale_id IS NOT NULL) AND invoice_number NOT LIKE "S%" ORDER BY id DESC'
        )
        return [dict(row) for row in ids]

    def link_barter(self, auction_id: int, sale_id: int) -> None:
        try:
            self.db.execute("INSERT INTO barter(auction_id, sale_id) VALUES (?,?)", (auction_id,sale_id))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to link barter | {e}")

    def unlink_barter(self, auction_id: int, sale_id: int) -> None:
        try:
            cursor = self.db.execute("DELETE FROM barter WHERE auction_id = ? AND sale_id = ?", (auction_id, sale_id))
            if cursor.rowcount != 1:
                self.db.rollback()
                raise ValueError(f"Barter link not found | {auction_id} and {sale_id}")
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to unlink barter | {e}")

    def change_barter_link(self, auction_id:int, sale_id: int, new_sale_id: int) -> None:
        try:
            cursor = self.db.execute("UPDATE barter SET sale_id = ? WHERE auction_id = ? AND sale_id = ?", (new_sale_id, auction_id, sale_id))
            if cursor.rowcount != 1:
                self.db.rollback()
                raise ValueError(f"Barter link not found | {auction_id} and {sale_id}")
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to change barter link | {e}")


