import datetime
import tradeTracker.services.models as models
import tradeTracker.CONSTANTS as CONSTANTS
import json

class SaleService:
    def __init__(self, db, receipt_service):
        self.db = db
        self.receipt_service = receipt_service

    def process_sale(self, sale_input) -> models.SaleResult:
        with self.db:  # sqlite transaction
            self._check_inventory(sale_input)
            print(sale_input)
            receipt = self.receipt_service.issue(sale_input)  # invoice teraz, ekasa neskôr
            sale_id = self._insert_sale_header(sale_input, receipt)
            self._insert_sale_items(sale_id, sale_input)
            return models.SaleResult(sale_id=sale_id, receipt=receipt)

    def _check_bulk_inventory(self,db, item_type, quantity_needed):
        """Check if sufficient inventory exists for the given item type."""
        result = db.execute(
            'SELECT SUM(quantity) FROM bulk_items WHERE item_type = ?',
            (item_type,)
        ).fetchone()
        available = result[0] if result[0] is not None else 0
        return available >= quantity_needed

    def _check_inventory(self,sale_input):
        bulk = sale_input.bulk
        if bulk and bulk.get('quantity', 0) > 0:
            if not self._check_bulk_inventory(self.db, 'bulk', bulk.get('quantity', 0)):
                raise ValueError       
        holo = sale_input.holo
        if holo and holo.get('quantity', 0) > 0:
            if not self._check_bulk_inventory(self.db, 'holo', holo.get('quantity', 0)):
                raise ValueError

        ex = sale_input.ex
        if ex and ex.get('quantity', 0) > 0:
            if not self._check_bulk_inventory(self.db, 'ex', ex.get('quantity', 0)):
                raise ValueError 

    def _insert_sale_header(self, sale_input, receipt):
        shippingPrice = None
        if sale_input.shipping:
            shippingPrice = sale_input.shipping.get('shippingPrice') 
        recieverInfoJson = json.dumps(sale_input.reciever)

        if shippingPrice == None:
            shippingPrice = 0   
        
        sale_date = datetime.date.today().isoformat()
        total_amount = round(float(sale_input.reciever.get('total')) + float(shippingPrice),2)
        invoice_num = receipt.number

        cursor = self.db.execute('INSERT INTO sales (invoice_number, sale_date, total_amount, notes, shipping_info) VALUES (?, ?, ?, ?,?)',
                (invoice_num, sale_date, total_amount, recieverInfoJson ,shippingPrice ))
        
        sale_id = cursor.lastrowid
        return sale_id

    def _insert_sale_items(self, sale_id, sale_input):
        cards = sale_input.cards
        sale_date = datetime.date.today().isoformat()
        if len(cards) > 0:
            for card in cards:
                sell_price = float(card.get('marketValue', 0))
                self.db.execute('UPDATE cards SET sold_date = ? WHERE id = ?',
                            (sale_date, card.get('cardId')))

                self.db.execute(
                        'INSERT INTO sale_items (sale_id, card_id, sell_price, profit) '
                        'VALUES (?, ?, ?, ? - (SELECT card_price FROM cards WHERE id = ?))',
                        (sale_id, card.get('cardId'), sell_price, sell_price, card.get('cardId'))
                        )
        sealed = sale_input.sealed
        if sealed:
            for item in sealed:
                self.db.execute('UPDATE sealed SET sale_id = ? WHERE id = ?',(sale_id, item.get("sid").replace('s','')))

        bulk = sale_input.bulk
        if bulk:
            self.db.execute('INSERT INTO bulk_sales (sale_id, item_type, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)',
                (sale_id, 'bulk', bulk.get('quantity', 0), bulk.get('unit_price', CONSTANTS.BULK_ITEM_UNIT_PRICES['bulk']), bulk.get('sell_price', 0)))
            # I am pretty sure the execudes are not needed
            self.db.execute('UPDATE bulk_counter SET counter = counter - ? WHERE counter_name = "bulk"', (bulk.get('quantity', 0),))
            # Deduct from bulk_items using FIFO
            self._deduct_bulk_items_fifo('bulk', bulk.get('quantity', 0))
            
        holo = sale_input.holo
        if holo:
            self.db.execute('INSERT INTO bulk_sales (sale_id, item_type, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)',
                (sale_id, 'holo', holo.get('quantity', 0), holo.get('unit_price', CONSTANTS.BULK_ITEM_UNIT_PRICES['holo']), holo.get('sell_price', 0)))
            self.db.execute('UPDATE bulk_counter SET counter = counter - ? WHERE counter_name = "holo"', (holo.get('quantity', 0),))
            # Deduct from bulk_items using FIFO
            self._deduct_bulk_items_fifo('holo', holo.get('quantity', 0))

        ex = sale_input.ex
        if ex:
            self.db.execute('INSERT INTO bulk_sales (sale_id, item_type, quantity, unit_price, total_price) VALUES (?, ?, ?, ?, ?)',
                (sale_id, 'ex', ex.get('quantity', 0), ex.get('unit_price', CONSTANTS.BULK_ITEM_UNIT_PRICES['ex']), ex.get('sell_price', 0)))
            self.db.execute('UPDATE bulk_counter SET counter = counter - ? WHERE counter_name = "ex"', (ex.get('quantity', 0),))
            self._deduct_bulk_items_fifo('ex', ex.get('quantity', 0))

        

    def _deduct_bulk_items_fifo(self, item_type, quantity_to_deduct):
        """Deduct bulk/holo items using FIFO (First In, First Out) from auctions."""
        remaining = quantity_to_deduct
        
        # Get all bulk_items for this type, ordered by auction_id (FIFO)
        items = self.db.execute(
            'SELECT id, auction_id, quantity FROM bulk_items '
            'WHERE item_type = ? ORDER BY auction_id ASC',
            (item_type,)
        ).fetchall()
        
        for item in items:
            if remaining <= 0:
                break
                
            item_id = item['id']
            current_quantity = item['quantity']
            
            if current_quantity <= remaining:
                # Delete this item entirely
                self.db.execute('DELETE FROM bulk_items WHERE id = ?', (item_id,))
                remaining -= current_quantity
            else:
                # Reduce quantity
                new_quantity = current_quantity - remaining
                self.db.execute(
                    'UPDATE bulk_items SET quantity = ?, total_price = quantity * unit_price '
                    'WHERE id = ?',
                    (new_quantity, item_id)
                )
                remaining = 0


