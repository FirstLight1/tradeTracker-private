import base64
from decimal import Decimal
from flask import request, Blueprint, jsonify, current_app, send_file, abort
from tradeTracker.db import get_db
from io import BytesIO
import datetime
from Crypto.Cipher import AES
import os
import fpdf
import json
import zipfile
import pandas as pd
import logging
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from . import generateInvoice, CONSTANTS, csrf
from tradeTracker.services.models import SaleInput
from tradeTracker.services.sale_service import SaleService
from tradeTracker.services.reciept_service import InvoiceReceiptService, EKasaReceiptService
from tradeTracker.services.cfAuth import verify_token, require_api_token

if os.environ.get("FLASK_ENV") != "production":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

bp = Blueprint('actions', __name__)
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)


dictKeys = ['Product ID', 'Name', 'Condition', 'Price', 'Card Number']
li = []
dataList = []
latest = None

conditionDict = {
    'MT' : "Mint",
    'NM' : "Near Mint",
    'EX' : "Excellent",
    'GD' : "Good",
    'LP' : "Light Played",
    'PL' : "Played",
    'PO' : "Poor"
}

def get_bulk_item_unit_price(item_type):
    return CONSTANTS.BULK_ITEM_UNIT_PRICES.get(item_type, 0)

def validate_and_sanitize_payments(payments):
    """
    Validate and sanitize payment data.
    Returns: (is_valid, sanitized_payments, error_message)
    """
    if payments is None or not isinstance(payments, list):
        return False, None, 'Invalid payments format'
    
    if len(payments) == 0:
        return False, None, 'At least one payment method required'
    
    if len(payments) > 10:  # Reasonable limit
        return False, None, 'Too many payment methods (max 10)'
    
    sanitized = []
    for payment in payments:
        if not isinstance(payment, dict):
            return False, None, 'Invalid payment object'
        
        payment_type = payment.get('type', '').strip()
        amount = 0
        try:
            if isinstance(payment.get('amount'), str):
                amount = payment.get('amount').replace(',','.')
            else:
                amount = payment.get('amount')
        except Exception as e:
            logger.warning("Failed to normalize amount '%s': %s", payment.get('amount'), e)
            amount = payment.get('amount')
        # Validate payment type against whitelist
        if payment_type not in CONSTANTS.ALLOWED_PAYMENT_TYPES:
            return False, None, f'Invalid payment type: {payment_type}'
        
        # Validate amount is a number
        try:
            amount = float(amount)
            if amount < 0:
                return False, None, 'Payment amount cannot be negative'
            if amount > 1000000:  # Reasonable limit
                return False, None, 'Payment amount too large'
        except (TypeError, ValueError) as e:
            logger.warning('Invalid payment amount | %s ',e) 
            return False, None, 'Invalid payment amount'
        amount = round(amount,2)
        sanitized.append({
            'type': payment_type,
            'amount': amount  # Ensure 2 decimal places
        })
    
    return True, sanitized, None

def loadExpansions():
    # Load expansion sets (works for both development and production)
    if os.getenv("FLASK_ENV") == "prod" and os.getenv("DATA_DIR"):
        data_dir = os.getenv("DATA_DIR")
        expansions_path = os.path.join(data_dir, "setAbbs.json")
    else:
        expansions_path = os.path.join(
            os.path.dirname(__file__),
            "data",
            "expansions",
            "setAbbs.json",
        )

    try:
        with open(expansions_path, mode='r', encoding='utf-8') as infile:
            data = json.load(infile)
            # Convert list of single-key dictionaries into one dictionary
            all_pokemon_sets = {}
            for item in data:
                for key, value in item.items():
                    all_pokemon_sets[key] = value
    except FileNotFoundError as e:
        print(f"Warning: Expansions file not found at {expansions_path}")
        logger.exception('File not found %s | %s ', expansions_path, e)
        all_pokemon_sets = {}

    return all_pokemon_sets

# Load the expansion sets at module import time
all_pokemon_sets = loadExpansions()


def migrate_payment_method(payment_method_text):
    """
    Migrate old space-separated payment method strings to JSON format.
    Returns: JSON string like '[{"type": "Hotovosť", "amount": 0}, {"type": "Barter", "amount": 0}]'
    """
    if not payment_method_text:
        return None
    
    # Check if already in JSON format
    try:
        parsed = json.loads(payment_method_text)
        if isinstance(parsed, list):
            return payment_method_text  # Already migrated
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Migrate old format (space-separated strings)
    payment_types = payment_method_text.strip().split()
    payments = [{"type": payment_type, "amount": 0} for payment_type in payment_types if payment_type]
    return json.dumps(payments)


def parse_payment_methods(payment_method_text):
    """
    Parse payment methods from database (handles both old and new formats).
    Returns: List of dicts [{"type": "...", "amount": ...}] or empty list
    """
    if not payment_method_text:
        return []
    
    try:
        parsed = json.loads(payment_method_text)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Fallback: old format - convert on the fly
    payment_types = payment_method_text.strip().split()
    return [{"type": payment_type, "amount": 0} for payment_type in payment_types if payment_type]


@bp.route('/add', methods=('POST',))
@verify_token
def add():
    if request.method == 'POST':
        cardsArr = request.get_json()
        db = get_db()
        auction = {
            'name': cardsArr[0]['name'] if 'name' in cardsArr[0] else None,
            'buy': cardsArr[0]['buy'] if 'buy' in cardsArr[0] else None,
            'date': cardsArr[0]['date'] if 'date' in cardsArr[0] else None,
            'payments': cardsArr[0]['payments'] if 'payments' in cardsArr[0] else None
        }
        
        # Validate and sanitize payments if provided
        payment_method_json = None
        if auction['payments']:
            is_valid, sanitized_payments, error_msg = validate_and_sanitize_payments(auction['payments'])
            if not is_valid:
                return jsonify({'status': 'error', 'message': f'{error_msg}, Error code: Ax01'}), 400
            payment_method_json = json.dumps(sanitized_payments)
        
        cursor = db.execute(
            'INSERT INTO auctions (auction_name, auction_price, date_created, payment_method) VALUES (?, ?, ?, ?)',
            (auction['name'], auction['buy'], auction['date'], payment_method_json)
        )
        auction_id = cursor.lastrowid
        for card in cardsArr[1:]:
            db.execute(
                'INSERT INTO cards (card_name, card_num, condition, card_price, market_value, auction_id) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (
                    card.get('cardName'),
                    card.get('cardNum'),
                    card.get('condition'),
                    card.get('buyPrice'),
                    card.get('marketValue'),
                    auction_id
                )
            )
        db.commit()
        return jsonify({'status': 'success', 'auction_id': auction_id}), 201
    
def _check_bulk_inventory(db, item_type, quantity_needed):
    """Check if sufficient inventory exists for the given item type."""
    result = db.execute(
        'SELECT SUM(quantity) FROM bulk_items WHERE item_type = ?',
        (item_type,)
    ).fetchone()
    available = result[0] if result[0] is not None else 0
    return available >= quantity_needed

def _deduct_bulk_items_fifo(db, item_type, quantity_to_deduct):
    """Deduct bulk/holo items using FIFO (First In, First Out) from auctions."""
    remaining = quantity_to_deduct
    
    # Get all bulk_items for this type, ordered by auction_id (FIFO)
    items = db.execute(
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
            db.execute('DELETE FROM bulk_items WHERE id = ?', (item_id,))
            remaining -= current_quantity
        else:
            # Reduce quantity
            new_quantity = current_quantity - remaining
            db.execute(
                'UPDATE bulk_items SET quantity = ?, total_price = quantity * unit_price '
                'WHERE id = ?',
                (new_quantity, item_id)
            )
            remaining = 0


def _normalize_decimal_input(value):
    if value is None:
        raise ValueError('Value is required')

    normalized = str(value).strip().replace(',', '.')
    if normalized == '':
        raise ValueError('Value is required')

    return normalized

def _add_bulk_items_helper(db, auction_id, bulk=None, holo=None, ex=None):
    """Helper function to add bulk items. Requires db connection to be passed in."""
    items_by_type = {
        'bulk': bulk,
        'holo': holo,
        'ex': ex,
    }
    parsed_items = []

    for expected_type, item_data in items_by_type.items():
        if item_data is None:
            continue

        item = dict(item_data)
        item_type = item.get('item_type', expected_type)
        if item_type not in CONSTANTS.BULK_ITEM_UNIT_PRICES:
            raise ValueError(f'Invalid item type: {item_type}')
        if item_type != expected_type:
            raise ValueError(f'Invalid payload for {expected_type}: got {item_type}')

        try:
            quantity = int(_normalize_decimal_input(item.get('quantity')))
            total_price = float(_normalize_decimal_input(item.get('total_price')))
        except (TypeError, ValueError):
            raise ValueError(f'Invalid quantity or sell price for {item_type}')

        if quantity <= 0:
            raise ValueError(f'Quantity for {item_type} must be greater than 0')

        try:
            unit_price_raw = item.get('unit_price')
            if unit_price_raw in (None, ''):
                unit_price = total_price / quantity
            else:
                unit_price = float(_normalize_decimal_input(unit_price_raw))
        except (TypeError, ValueError):
            unit_price = total_price / quantity

        parsed_items.append({
            'item_type': item_type,
            'quantity': quantity,
            'unit_price': unit_price,
            'total_price': total_price,
        })

    for item in parsed_items:
        db.execute(
            'INSERT INTO bulk_items (auction_id, item_type, quantity, unit_price, total_price) '
            'VALUES (?, ?, ?, ?, ?) ON CONFLICT(auction_id, item_type) DO UPDATE SET '
            'quantity = quantity + excluded.quantity, '
            'total_price = total_price + excluded.total_price, '
            'unit_price = (total_price + excluded.total_price) / (quantity + excluded.quantity)',
            (
                auction_id,
                item['item_type'],
                item['quantity'],
                item['unit_price'],
                item['total_price']
            )
        )

@bp.route('/addBulkItems/<int:auction_id>', methods=('POST',))
@verify_token
def addBulkItems(auction_id):
    """Route handler for adding bulk items."""
    data = request.get_json()
    bulk = data.get('bulk')
    holo = data.get('holo')
    ex = data.get('ex')
    db = get_db()
    try:
        _add_bulk_items_helper(db, auction_id, bulk, holo, ex)
    except ValueError as e:
        db.rollback()
        logger.exception('failed to add to auction | auction_id : %s', auction_id)
        return jsonify({'status': 'error', 'message': f'{str(e)}, Error code: Ax02'}), 400
    db.commit()
    return jsonify({'status': 'success'}), 201

@bp.route('/loadAuctions', methods=('GET',))
@verify_token
def loadAuctions():
    db = get_db()
    auctions = db.execute(
        'SELECT DISTINCT a.*, b.sale_id, s.invoice_number FROM auctions a '
        'LEFT JOIN barter b ON b.auction_id = a.id '
        'LEFT JOIN sales s ON b.sale_id = s.id '
        'LEFT JOIN cards c ON a.id = c.auction_id '
        'LEFT JOIN sale_items si ON c.id = si.card_id '
        'WHERE a.id = 1 OR si.card_id IS NULL '
        'ORDER BY (a.id = 1) DESC, '
        'a.id DESC '
    ).fetchall()
    
    # Auto-migrate payment_method data on load
    auctions_list = []
    for auction in auctions:
        auction_dict = dict(auction)
        if auction_dict.get('payment_method'):
            # Check if migration needed
            migrated = migrate_payment_method(auction_dict['payment_method'])
            if migrated != auction_dict['payment_method']:
                # Update database with migrated value
                db.execute('UPDATE auctions SET payment_method = ? WHERE id = ?', 
                          (migrated, auction_dict['id']))
                auction_dict['payment_method'] = migrated
        auctions_list.append(auction_dict)
    db.commit()
    return jsonify(auctions_list)

@bp.route('/loadSealed', methods=('GET',))
@verify_token
def loadSealed():
    db = get_db()

    sealed_products =  db.execute("SELECT 's' || id as sid, name, price, market_value, date FROM sealed WHERE sale_id is NULL AND auction_id is NULL").fetchall()
    return jsonify({'status':'success', 'data' : [dict(product) for product in sealed_products]})

@bp.route('/addSealed', methods=('POST',))
@verify_token
def addSealed():
    data = request.get_json()
    db = get_db()
    
    for sealed in data:
        marketValue = float(sealed.get("market_value").replace(',','.')) if sealed.get("market_value") is not None else 0
        price = float(sealed.get("price").replace(',','.')) if sealed.get("price") is not None else marketValue * 0.80;
        date = sealed.get('dateAdded') if sealed.get('dateAdded') is not None else datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
        db.execute("INSERT INTO sealed(name, price, market_value, date) VALUES (?, ?, ?, ?)",(sealed.get("name"), price, marketValue, date))
    db.commit()
    return jsonify({'status':'success'}),200


@bp.route('/loadCards/<int:auction_id>',methods=('GET',))
@verify_token
def loadCards(auction_id):
    db = get_db()
    cards = db.execute(
        'SELECT c.* FROM cards c '
        'LEFT JOIN sale_items si ON c.id = si.card_id '
        'WHERE c.auction_id = ? AND si.card_id IS NULL', (auction_id,)).fetchall()
    return jsonify([dict(card) for card in cards]),200

@bp.route('/loadBulk/<int:auction_id>', methods=('GET',))
@verify_token
def loadBulk(auction_id):
    db = get_db()

    bulk_items = db.execute(
        'SELECT bi.* FROM bulk_items bi '
        'WHERE bi.auction_id = ?', (auction_id,)).fetchall()
    return jsonify([dict(item) for item in bulk_items]),200

@bp.route('/loadSealed/<int:auction_id>', methods=('GET',))
@verify_token
def loadSealedByAuction(auction_id):
    db = get_db()
    sealed_items = db.execute(
        "SELECT 's' || id as sid, name, price, market_value, date FROM sealed "
        "WHERE auction_id = ? AND sale_id is NULL", 
        (auction_id,)
    ).fetchall()
    return jsonify([dict(item) for item in sealed_items]), 200

@bp.route('/loadAllCards/<int:auction_id>', methods=('GET',))
@verify_token
def loadAllCards(auction_id):
    db = get_db()
    cards = db.execute('SELECT * FROM cards WHERE auction_id = ?', (auction_id,)).fetchall()
    return jsonify([dict(card) for card in cards]),200

@bp.route('/inventoryValue', methods=('GET',))
@verify_token
def invertoryValue():
    db = get_db()
    cur = db.cursor()
    cardMarketValue = cur.execute('SELECT SUM(market_value) FROM cards c LEFT JOIN sale_items si ON c.id = si.card_id WHERE si.card_id IS NULL').fetchone()[0]
    bulkValue = cur.execute('SELECT SUM(total_price) FROM bulk_items').fetchone()[0]
    sealedValue = cur.execute('SELECT SUM(market_value) FROM sealed WHERE sale_id IS NULL').fetchone()[0]
    value = (cardMarketValue if cardMarketValue is not None else 0) + (bulkValue if bulkValue is not None else 0) + (sealedValue if sealedValue is not None else 0)

    return jsonify({'status': 'success','value': value}),200


@bp.route('/deleteCard/<int:card_id>', methods=('DELETE',))
@verify_token
def deleteCard(card_id):
    db = get_db()
    db.execute('DELETE FROM cards WHERE id = ?', (card_id,))
    db.commit()
    return jsonify({'status' : 'success'})

@bp.route('/deleteBulkItem/<int:item_id>', methods=('DELETE',))
@verify_token
def deleteBulkItem(item_id):
    db = get_db()
    db.execute('DELETE FROM bulk_items WHERE id = ?', (item_id,))
    db.commit()
    return jsonify({'status' : 'success'})

@bp.route('/deleteSealed/<string:sid>', methods=('DELETE',))
@verify_token
def deleteSealed(sid):
    id = sid.replace('s', '')
    db = get_db()
    db.execute('DELETE FROM sealed WHERE id = ?',(id,))
    db.commit()
    return jsonify({'status' : 'success'})

@bp.route('/deleteAuction/<int:auction_id>', methods=('DELETE',))
@verify_token
def deleteAuction(auction_id):
    db = get_db()
    db.execute('DELETE FROM bulk_items WHERE auction_id = ?', (auction_id,))
    db.execute('DELETE FROM cards WHERE auction_id = ?', (auction_id,))
    db.execute('DELETE FROM auctions WHERE id = ?', (auction_id,))
    db.execute('DELETE from sealed WHERE auction_id = ?', (auction_id,))
    db.commit()
    return jsonify({'status': 'success'}),200

@bp.route('/update/<int:card_id>', methods=('PATCH',))
@verify_token
def update(card_id):
    db = get_db()
    data = request.get_json()
    field = data.get("field")
    value = data.get("value")
    allowed_fields = {"card_name", "card_num", "condition", "card_price", "market_value"}

    if field == 'sold' or field == 'sold_cm':
        db.execute(f'UPDATE sale_items SET {field} = ? WHERE card_id = ?', (value, card_id))
        db.commit()
        return jsonify({'status': 'success'}),200

    if field in allowed_fields:
        db.execute(f'UPDATE cards SET {field} = ? WHERE id = ?', (value, card_id))
        db.commit()
    return jsonify({'status': 'success'}),200

@bp.route('/addToExistingAuction/<int:auction_id>', methods=('POST',))
@verify_token
def addToExistingAuction(auction_id):
    if request.method == 'POST':
        data = request.get_json()
        cards = data.get('cards', [])
        db = get_db()
        try:
            for card in cards:
                db.execute('INSERT INTO cards (card_name, card_num, condition, card_price, market_value, auction_id)'
                ' VALUES (?, ?, ?, ?, ?, ?)',
                (
                    card.get('cardName'),
                    card.get('cardNum'),
                    card.get('condition'),
                    card.get('buyPrice'),
                    card.get('marketValue'),
                    auction_id
                )
            )

            # Handle sealed items
            sealed = data.get('sealed', [])
            if sealed:
                for item in sealed:
                    marketValue = float(item.get("market_value").replace(',','.')) if item.get("market_value") is not None else 0
                    price = float(item.get("price").replace(',','.')) if item.get("price") is not None else marketValue * 0.80
                    date = item.get('date') if item.get('date') is not None else datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
                    db.execute(
                        "INSERT INTO sealed(name, price, market_value, date, auction_id) VALUES (?, ?, ?, ?, ?)",
                        (item.get("name"), price, marketValue, date, auction_id)
                    )

            bulk = data.get('bulk')
            holo = data.get('holo')
            ex = data.get('ex')
            if bulk or holo or ex:
                _add_bulk_items_helper(db, auction_id, bulk, holo, ex)

            db.commit()
            return jsonify({'status': 'success'}), 201
        except ValueError as e:
            db.rollback()
            logger.exception(
                'Failed to add to existing auction | auction_id: %s | reason: %s',
                auction_id,
                e,
            )
            return jsonify({'status': 'error', 'message': f'{str(e)}, Error code: Ax03'}), 400

@bp.route('/bulkCounterValue', methods = ('GET',))
@verify_token
def bulkCounterValue():
    db = get_db()
    cur = db.cursor()
    result = cur.execute('SELECT sum(quantity) as total, item_type FROM bulk_items GROUP BY item_type ORDER BY item_type').fetchall()
    counters = {row['item_type']: row['total'] for row in result}
    bulk_counter = counters.get('bulk', 0)
    holo_counter = counters.get('holo', 0)
    ex_counter = counters.get('ex', 0)
   
    return jsonify({'status': 'success','bulk_counter': bulk_counter, 'holo_counter': holo_counter, 'ex_counter': ex_counter}),200

@bp.route('/loadSoldHistory', methods = ('GET',))
@verify_token
def loadSoldHistory():
    db = get_db()
    sales = db.execute(
        'SELECT s.*, '
        '(COALESCE((SELECT SUM(si.profit) FROM sale_items si WHERE si.sale_id = s.id), 0) + '
        'COALESCE((SELECT SUM(market_value - price) FROM sealed WHERE sale_id = s.id),0) + '
        'COALESCE((SELECT SUM(bs.total_price - bs.quantity * bs.unit_price) FROM bulk_sales bs WHERE bs.sale_id = s.id), 0)) '
        'as total_profit, b.auction_id '
        'FROM sales s '
        'LEFT JOIN barter b ON b.sale_id = s.id '
        'ORDER BY sale_date DESC'
    ).fetchall()
    result = []

    for sale in sales:
        sale = dict(sale) 
        try: 
            crypt = json.loads(sale['notes'])

            nonce = base64.b64decode(crypt["nonce"])
            ciphertext = base64.b64decode(crypt["ciphertext"])
            tag = base64.b64decode(crypt["tag"])
            key = base64.b64decode(os.environ['KEY'])
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

            decrypted_bytes = cipher.decrypt_and_verify(ciphertext, tag)
            data = decrypted_bytes.decode("utf-8")
            sale['notes'] = data
            result.append(sale)
        except Exception as e:
            result.append(sale)
    return jsonify(result)
    
@bp.route('/loadSoldCards/<int:sale_id>', methods=('GET',))
@verify_token
def loadSoldCards(sale_id):
    db = get_db()

    cards = db.execute(
        'SELECT c.*, si.sell_price as invoice_sell_price, si.sold_cm, si.sold, s.sale_date, s.invoice_number '
        'FROM cards c '
        'JOIN sale_items si ON c.id = si.card_id '
        'JOIN sales s ON si.sale_id = s.id '
        'WHERE si.sale_id = ?',
        (sale_id,)
    ).fetchall()

    sealed_sales = db.execute('SELECT * FROM sealed WHERE sale_id = ?', (sale_id,))
    sealed_sales_list = [dict(item) for item in sealed_sales]

    bulk_sales = db.execute(
        'SELECT * FROM bulk_sales WHERE sale_id = ?', (sale_id,))
    bulk_sales_list = [dict(bulk) for bulk in bulk_sales]
    response = {
        "cards": [dict(card) for card in cards],
        "sealed": sealed_sales_list,
        "bulk_sales": bulk_sales_list
    }

    return jsonify(response)

@bp.route('/unlinkedBarterIds',methods=('GET',))
@verify_token
def unlinkedBarterIds():
    db = get_db()
    ids = db.execute('SELECT id, invoice_number FROM sales WHERE id NOT IN (SELECT sale_id FROM barter WHERE sale_id IS NOT NULL) AND invoice_number NOT LIKE "S%" ORDER BY id DESC')
    return jsonify({'status': 'success', 'data': [dict(row) for row in ids]})

@bp.route('/linkAuctionToSale/<int:auction_id>',methods=('POST',))
@verify_token
def linkAuctionToSale(auction_id):
    db = get_db()
    id = request.get_json()
    
    db.execute('INSERT INTO barter(auction_id, sale_id) VALUES (?,?)',(auction_id, id['sale_id']))
    db.commit()

    return jsonify({'status': 'success'})

@bp.route('/orderReturn/<int:saleId>', methods=('POST',))
@verify_token
def orderReturn(saleId):
    db = get_db()

    try:
        db.execute('UPDATE cards SET sold_date = NULL WHERE id IN (SELECT card_id FROM sale_items WHERE sale_id = ?)',(saleId, ))
        bulk_sales_rows = db.execute(
            'SELECT item_type, quantity FROM bulk_sales WHERE sale_id = ?', (saleId,)
        ).fetchall()
        for bs_row in bulk_sales_rows:
            target = db.execute(
                'SELECT id FROM bulk_items WHERE item_type = ? ORDER BY auction_id DESC LIMIT 1',
                (bs_row['item_type'],)
            ).fetchone()
            if target:
                db.execute(
                    'UPDATE bulk_items SET quantity = quantity + ? WHERE id = ?',
                    (bs_row['quantity'], target['id'])
                )
        db.execute('DELETE FROM sales WHERE id = ?', (saleId, ))
    except:
         db.rollback()
         logger.exception('Return creation failed | saleId: %s', saleId)
         return jsonify({'status': 'error', 'message': 'There was an error while creating a return, Error code: Ax04'}), 400 
    
    db.commit()
    return jsonify({'status': 'success'}),200


@bp.route('/generateCreditNote/<int:saleId>', methods=('POST',))
@verify_token
def generate_credit_note(saleId):
    db = get_db()

    # Load the sale record (contains receiver info in notes and invoice_number)
    sale = db.execute('SELECT * FROM sales WHERE id = ?', (saleId,)).fetchone()
    if sale is None:
        return jsonify({'status': 'error', 'message': 'Sale not found, Error code: Ax05'}), 404

    # Parse receiver info stored as JSON in the notes column
    try:
        crypt = json.loads(sale['notes'])
        nonce = base64.b64decode(crypt['nonce'])
        cipherText = base64.b64decode(crypt['ciphertext'])
        tag = base64.b64decode(crypt['tag'])
        key = base64.b64decode(os.environ['KEY'])
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        decrypted = cipher.decrypt_and_verify(cipherText, tag)
        reciever = json.loads(decrypted.decode("utf-8"))
    except (json.JSONDecodeError, TypeError):
        reciever = {}

    original_invoice_num = sale['invoice_number']

    # Load cards
    cards_rows = db.execute(
        'SELECT c.card_name, c.card_num, si.sell_price as marketValue '
        'FROM cards c '
        'JOIN sale_items si ON c.id = si.card_id '
        'WHERE si.sale_id = ?',
        (saleId,)
    ).fetchall()
    items = [{'cardName': r['card_name'], 'cardNum': r['card_num'], 'marketValue': r['marketValue']} for r in cards_rows]

    # Load sealed items
    sealed_rows = db.execute('SELECT * FROM sealed WHERE sale_id = ?', (saleId,)).fetchall()
    sealed = [{'sealedName': r['name'], 'marketValue': r['market_value'], 'auctionId': r['auction_id']} for r in sealed_rows]

    # Load bulk/holo/ex sales
    bulk_rows = db.execute('SELECT * FROM bulk_sales WHERE sale_id = ?', (saleId,)).fetchall()
    bulk = None
    holo = None
    ex = None
    for b in bulk_rows:
        if b['item_type'] == 'bulk':
            bulk = {'quantity': b['quantity'], 'unit_price': b['unit_price']}
        elif b['item_type'] == 'holo':
            holo = {'quantity': b['quantity'], 'unit_price': b['unit_price']}
        elif b['item_type'] == 'ex':
            ex = {'quantity': b['quantity'], 'unit_price': b['unit_price']}

    # Load shipping info
    shipping = None
    if sale['shipping_info'] and float(sale['shipping_info']) > 0:
        shipping = {
            'shippingWay': 'Doprava / Poštovné – samostatná služba',
            'shippingPrice': sale['shipping_info']
        }

    # Reconstruct payment methods from receiver info if available
    payment_methods = reciever.get('paymentMethods') or []
    if not payment_methods and reciever.get('paymentMethod'):
        payment_methods = [{'type': reciever.get('paymentMethod'), 'amount': 0}]

    try:
        pdf, cn_num = generateInvoice.generateCreditNote(
            reciever,
            items if items else None,
            sealed if sealed else None,
            bulk,
            holo,
            ex,
            payment_methods if payment_methods else None,
            shipping,
            original_invoice_num
        )
        response = send_file(
                        BytesIO(pdf['bytes']),
                        download_name=pdf['filename'],
                        as_attachment=True,
                        mimetype='application/pdf'
                        )

    except Exception as e:
        logger.critical('Credit note generation failed %s', e)
        return jsonify({'status': 'error', 'message': f'{str(e)}, Error code: Ax06'}), 500
    logger.info('Credit note generated succesfully | original invoice num: %s', original_invoice_num)
    return response 


@bp.route('/generateSoldReport', methods=('GET',))
@limiter.limit("2 per minute")
@verify_token
def generateSoldReport():
    db = get_db()
    month = request.args.get('month').zfill(2)
    year = request.args.get('year')
    cards = db.execute(
        'SELECT c.card_name, c.card_num, c.card_price, si.sell_price '
        'FROM cards c '
        'JOIN sale_items si ON c.id = si.card_id '
        'JOIN sales s ON si.sale_id = s.id '
        'WHERE strftime("%Y", s.sale_date) = ? AND strftime("%m", s.sale_date) = ?', 
        (year, month)).fetchall()
   
    sealed = db.execute('SELECT se.name, se.price, se.market_value, se.auction_id FROM sealed se JOIN sales s ON se.sale_id = s.id WHERE strftime("%Y", s.sale_date) = ? AND strftime("%m", s.sale_date) = ? ',
                        (year, month)).fetchall()
    sealedList = [dict(item) for item in sealed]

    bulkHolo = db.execute(
        'SELECT item_type, SUM(bs.quantity) as quantity, SUM(bs.total_price) as total_price FROM bulk_sales bs '
        'JOIN sales s ON bs.sale_id = s.id '
        'WHERE strftime("%Y", s.sale_date) = ? AND strftime("%m", s.sale_date) = ?'
        ' GROUP BY bs.item_type',
        (year, month)).fetchall()

    shipping = db.execute('SELECT shipping_info FROM sales WHERE strftime("%Y", sale_date) = ? AND strftime("%m", sale_date) = ?', 
        (year, month)).fetchall() 
    
    shipping_list = []
    for s in shipping:
        temp = dict(s)
        shipping_list.append(temp['shipping_info']) if temp['shipping_info'] is not None else 0
    # Convert to list of dicts for easier processing
    cards_list = [dict(card) for card in cards]

    bulkAndHoloList = []
    i = 0
    for item_type in bulkHolo:
        bulkAndHoloList.append(dict(item_type))
        bulkAndHoloList[i].update({'buy_price': get_bulk_item_unit_price(item_type['item_type'])})
        i += 1

    try:
        pdf_path = generatePDF(month, year, cards_list, sealedList, bulkAndHoloList, shipping_list)
        xls_path = createBuyReport(month, year, db);
        logger.info('Sold report generated succesfully | month: %s | year: %s', month, year)

        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(pdf_path, arcname=os.path.basename(pdf_path))
            zip_file.write(xls_path, arcname=os.path.basename(xls_path))
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=f"SoldReport_{month}_{year}.zip",
            mimetype="application/zip"
        )

    except Exception as e:
        logger.exception('PDF generation failed')
        print(f"Error generating PDF: {e}")
        return jsonify({'status': 'error', 'message': f'{str(e)}, Error code: Ax08'}), 500


def generatePDF(month, year, cards, sealed,bulkAndHoloList, shipping):
    # Determine the save path based on environment
    if os.getenv("FLASK_ENV") == "prod":
        data_dir = os.getenv("DATA_DIR", current_app.instance_path)
        app_data_dir = os.path.join(data_dir, 'Reports')
        os.makedirs(app_data_dir, exist_ok=True)
        pdf_path = os.path.join(app_data_dir, f'Report_{month}_{year}.pdf')
    else:
        # Running in development
        reports_dir = os.path.join(current_app.instance_path, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        pdf_path = os.path.join(reports_dir, f'Report_{month}_{year}.pdf')

    font_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    
    # Create PDF
    pdf = fpdf.FPDF()
    pdf.add_page()
    
    # Add Unicode-compatible font
    font_family = 'DejaVu'
    pdf.add_font(font_family, '', os.path.join(font_dir, 'DejaVuSans.ttf'), uni=True)
    pdf.add_font(font_family, 'B', os.path.join(font_dir, 'DejaVuSans-Bold.ttf'), uni=True)

    # Set title
    pdf.set_font(font_family, '', 16)
    pdf.cell(0, 10, f'Sales Report - {month}/{year}', 0, 1, 'C')
    pdf.ln(10)
    
    # Add summary
    pdf.set_font(font_family, '', 12)
    pdf.cell(0, 10, f'Total Cards Sold: {len(cards) + sum(item["quantity"] for item in bulkAndHoloList) + len(sealed)}', 0, 1)
    pdf.ln(5)
    
    # Calculate totals
    total_buy_price = (
        sum(card['card_price'] or 0 for card in cards)
        + sum(item['price'] or 0 for item in sealed)
        + sum(item['quantity'] * get_bulk_item_unit_price(item['item_type']) for item in bulkAndHoloList)
    )
    total_sell_price = sum(card['sell_price'] or 0 for card in cards) + sum(item['market_value'] or 0 for item in sealed) + sum(item['total_price'] or 0 for item in bulkAndHoloList)
    total_profit = total_sell_price - total_buy_price
    total_neg_margin = 0
    total_pos_margin = 0
    total_shipping_with_VAT = 0
    total_shipping_without_VAT = 0
    total_shipping_VAT = 0
    for card in cards:
        curr_margin = Decimal(card['sell_price'] - card['card_price']) 
        if curr_margin > 0:
            total_pos_margin += curr_margin
        else:
            total_neg_margin += curr_margin

    for item in sealed:
        if item['auction_id'] is not None:
            curr_margin = Decimal(item['market_value'] - item['price'])
            if curr_margin > 0:
                total_pos_margin += curr_margin
            else:
                total_neg_margin += curr_margin

    for item in bulkAndHoloList:
        unit_price = get_bulk_item_unit_price(item['item_type'])
        total_pos_margin += Decimal(item['total_price'] - item['quantity'] * unit_price)

    for s in shipping:
        s = Decimal(s)
        removeVat = Decimal(1.23)
        total_shipping_with_VAT += s
        total_shipping_without_VAT += Decimal(s / removeVat)
        total_shipping_VAT += Decimal(s - (s / removeVat))
    
    pdf.cell(0, 8, f'Total Buy Price: {total_buy_price:.2f}€', 0, 1)
    pdf.cell(0, 8, f'Total Sell Price: {total_sell_price:.2f}€', 0, 1)
    pdf.cell(0, 8, f'Total Profit: {total_profit:.2f}€', 0, 1)
    pdf.cell(0, 8, f'Total Negative Margin: {total_neg_margin:.2f}€', 0, 1)
    pdf.cell(0, 8, f'Total Positive Margin: {total_pos_margin:.2f}€', 0, 1)
    pdf.cell(0, 8, f'Shipping + DPH: {total_shipping_with_VAT:.2f}€', 0, 1)
    pdf.cell(0, 8, f'Shipping: {total_shipping_without_VAT:.2f}€', 0, 1)
    pdf.cell(0, 8, f'Shipping DPH: {total_shipping_VAT:.2f}€', 0, 1)
    pdf.ln(10)

    # Add bulk and holo summary
    # Table header for bulk and holo
    pdf.set_font(font_family, '', 10)
    pdf.cell(50, 10, 'Item type', 1, 0, 'C')
    pdf.cell(35, 10, 'Quantity', 1, 0, 'C')
    pdf.cell(30, 10, 'Buy Price', 1, 0, 'C')
    pdf.cell(30, 10, 'Total Price', 1, 0, 'C')
    pdf.cell(30, 10, 'Margin', 1, 0, 'C')
    pdf.ln()

    # Table content for bulk and holo
    pdf.set_font(font_family, '', 9)
    for item in bulkAndHoloList:
        item_type = item['item_type'] or 'N/A'
        quantity = str(item['quantity']) if item['quantity'] else 'N/A'
        buy_price = f"{item['buy_price']:.2f}€" if item['buy_price'] else 'N/A'
        total_price = f"{item['total_price']:.2f}€" if item['total_price'] else 'N/A'
        margin = f"{(item['total_price'] - (item['quantity'] * item['buy_price'])):.2f}€" if item['total_price'] and item['buy_price'] else 'N/A'

        pdf.cell(50, 8, item_type, 1, 0, 'L')
        pdf.cell(35, 8, quantity, 1, 0, 'C')
        pdf.cell(30, 8, buy_price, 1, 0, 'R')
        pdf.cell(30, 8, total_price, 1, 0, 'R')
        pdf.cell(30, 8, margin, 1, 0, 'R')
        pdf.ln()

    
    # Table header
    pdf.set_font(font_family, '', 10)
    pdf.cell(50, 10, 'Card Name', 1, 0, 'C')
    pdf.cell(35, 10, 'Card Number', 1, 0, 'C')
    pdf.cell(30, 10, 'Buy Price', 1, 0, 'C')
    pdf.cell(30, 10, 'Sell Price', 1, 0, 'C')
    pdf.cell(30, 10, 'Margin', 1, 0, 'C')
    pdf.ln()
    
    # Table content
    pdf.set_font(font_family, '', 9)
    for card in cards:
        card_name = card['card_name'] or 'N/A'
        card_num = card['card_num'] or 'N/A'
        buy_price = f"{card['card_price']:.2f}€" if card['card_price'] else 'N/A'
        sell_price = f"{card['sell_price']:.2f}€" if card['sell_price'] else 'N/A'
        card_profit = f"{(card['sell_price'] - card['card_price']):.2f}€" if card['sell_price'] and card['card_price'] else 'N/A'
        
        # Estimate height needed for card name (more conservative)
        # With font size 9 and line height 4, approximately 25 chars per line in 50mm width
        chars_per_line = 25
        estimated_lines = max(1, (len(card_name) + chars_per_line - 1) // chars_per_line)
        estimated_height = estimated_lines * 4
        
        # Check if we need a page break BEFORE drawing anything
        if pdf.get_y() + estimated_height > pdf.h - pdf.b_margin - 10:
            pdf.add_page()
            # Redraw table header on new page
            pdf.set_font(font_family, '', 10)
            pdf.cell(50, 10, 'Card Name', 1, 0, 'C')
            pdf.cell(35, 10, 'Card Number', 1, 0, 'C')
            pdf.cell(30, 10, 'Buy Price', 1, 0, 'C')
            pdf.cell(30, 10, 'Sell Price', 1, 0, 'C')
            pdf.cell(30, 10, 'Margin', 1, 0, 'C')
            pdf.ln()
            pdf.set_font(font_family, '', 9)
        
        # Store starting position
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # Draw card name with multi_cell
        pdf.multi_cell(50, 4, card_name, border=1, align='L')
        
        # Calculate actual height used
        y_after_name = pdf.get_y()
        actual_height = y_after_name - y_start
        
        # Draw other cells aligned with the card name
        pdf.set_xy(x_start + 50, y_start)
        pdf.cell(35, actual_height, card_num, 1, 0, 'C')
        pdf.cell(30, actual_height, buy_price, 1, 0, 'R')
        pdf.cell(30, actual_height, sell_price, 1, 0, 'R')
        pdf.cell(30, actual_height, card_profit, 1, 0, 'R')
        
        # Move to next row
        pdf.set_xy(x_start, y_after_name)
    
    # Table header
    pdf.set_font(font_family, '', 10)
    pdf.cell(85, 10, 'Product Name', 1, 0, 'C')
    pdf.cell(30, 10, 'Buy Price', 1, 0, 'C')
    pdf.cell(30, 10, 'Sell Price', 1, 0, 'C')
    pdf.cell(30, 10, 'Margin', 1, 0, 'C')
    pdf.ln()
    
    # Table content
    # Sealed items   
    pdf.set_font(font_family, '', 9)
    for item in sealed:
        name = item['name'] or 'N/A'
        buy_price = f"{item['price']:.2f}€" if item['price'] else 'N/A'
        sell_price = f"{item['market_value']:.2f}€" if item['market_value'] else 'N/A'
        card_profit = f"{(item['market_value'] - item['price']):.2f}€" if item['market_value'] and item['price'] else 'N/A'
        
        # Estimate height needed for product name
        # With font size 9 and line height 4, approximately 40 chars per line in 85mm width
        chars_per_line = 40
        estimated_lines = max(1, (len(name) + chars_per_line - 1) // chars_per_line)
        estimated_height = estimated_lines * 4
        
        # Check if we need a page break BEFORE drawing anything
        if pdf.get_y() + estimated_height > pdf.h - pdf.b_margin - 10:
            pdf.add_page()
            # Redraw table header on new page
            pdf.set_font(font_family, '', 10)
            pdf.cell(85, 10, 'Product Name', 1, 0, 'C')
            pdf.cell(30, 10, 'Buy Price', 1, 0, 'C')
            pdf.cell(30, 10, 'Sell Price', 1, 0, 'C')
            pdf.cell(30, 10, 'Margin', 1, 0, 'C')
            pdf.ln()
            pdf.set_font(font_family, '', 9)
        
        # Store starting position
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # Draw product name with multi_cell
        pdf.multi_cell(85, 4, name, border=1, align='L')
        
        # Calculate actual height used
        y_after_name = pdf.get_y()
        actual_height = y_after_name - y_start
        
        # Draw other cells aligned with the product name
        pdf.set_xy(x_start + 85, y_start)
        pdf.cell(30, actual_height, buy_price, 1, 0, 'R')
        pdf.cell(30, actual_height, sell_price, 1, 0, 'R')
        pdf.cell(30, actual_height, card_profit, 1, 0, 'R')
        
        # Move to next row
        pdf.set_xy(x_start, y_after_name)
    # Save PDF
    pdf.output(pdf_path)
    return pdf_path

def createBuyReport(month, year, db):
    if os.getenv("FLASK_ENV") == "prod":
        data_dir = os.getenv("DATA_DIR", current_app.instance_path)
        app_data_dir = os.path.join(data_dir, 'Reports')
        os.makedirs(app_data_dir, exist_ok=True)
        xls_path = os.path.join(app_data_dir, f'Nakupy_{month}_{year}.xlsx')
    else:
        # Running in development
        reports_dir = os.path.join(current_app.instance_path, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        xls_path = os.path.join(reports_dir, f'Nakupy_{month}_{year}.xlsx')

    rows = db.execute('SELECT auction_name,auction_price, date_created, payment_method FROM auctions WHERE strftime("%Y", substr(date_created, 1, 19)) = ? AND strftime("%m", substr(date_created, 1, 19)) = ? ',(year,month)).fetchall()

    bought = {
            'Meno': [],
            'Cena': [],
            'Datum':[],
            'Payment type':[],
            'Amount':[]
            } 

    for row in rows:
        bought['Meno'].append(row['auction_name'])
        try:
            bought['Cena'].append(Decimal(row['auction_price']))
        except:
            bought['Cena'].append('Error')
        date = datetime.datetime.strptime( row['date_created'].split('T')[0], '%Y-%m-%d')
        formatedDate = date.strftime('%d.%m.%Y')
        bought['Datum'].append(formatedDate)
        if row['payment_method'] != None:
            payments = json.loads(row['payment_method'])
            bought['Payment type'].append(', '.join(payment['type'] for payment in payments))
            bought['Amount'].append(', '.join(str(payment['amount']) for payment in payments))
        else:
            bought['Payment type'].append('')
            bought['Amount'].append('')

    df = pd.DataFrame(bought)

    with pd.ExcelWriter(xls_path) as writer:
        df.to_excel(writer, sheet_name='nakupy', index=False)

        worksheet = writer.sheets['nakupy']
        worksheet.column_dimensions['A'].width = 24
        worksheet.column_dimensions['B'].width = 12
        worksheet.column_dimensions['C'].width = 11
        worksheet.column_dimensions['D'].width = 30
        worksheet.column_dimensions['E'].width = 20

        for row in range(2, len(df) + 2):
            cell = worksheet[f'B{row}']
            cell.number_format = '#,##.00 "€"'

        for row in range(2, len(df) + 2):
            cell = worksheet[f'D{row}']
            cell.number_format = '#,##.00 "€"'
        
    
    return xls_path

@bp.route('/addToCollection', methods=('POST',))
@verify_token
def addToCollection():
    if request.method == 'POST':
        cards = request.get_json()
        db = get_db()
        for card in cards:
            db.execute('INSERT INTO collection (card_name, card_num, condition, buy_price, market_value)'
            ' VALUES (?, ?, ?, ?, ?)',
            (
                card.get('cardName'),
                card.get('cardNum'),
                card.get('condition'),
                card.get('buyPrice'),
                card.get('marketValue'),
            )
        )
        db.commit()
    return jsonify({'status': 'success'}), 201

@bp.route('/loadCollection', methods=('GET',))
@verify_token
def loadCollection():
    db = get_db()
    cards = db.execute('SELECT * FROM collection').fetchall()
    return jsonify([dict(card) for card in cards])

@bp.route('/deleteFromCollection/<int:card_id>', methods=('DELETE',))
@verify_token
def deleteFromCollection(card_id):
    db = get_db()
    db.execute('DELETE FROM collection WHERE id = ?', (card_id, ))
    db.commit()
    return jsonify({'status': 'success'}), 200

@bp.route('/updateCollection/<int:card_id>', methods=('PATCH',))
@verify_token
def updateCollection(card_id):
    db = get_db()
    data = request.get_json()
    field = data.get("field")
    value = data.get("value")
    allowed_fields = {"card_name", "card_num", "condition", "buy_price","market_value"}

    if field in allowed_fields:
        db.execute(f'UPDATE collection SET {field} = ? WHERE id = ?', (value, card_id))
        db.commit()
    return jsonify({'status': 'success'}),200

@bp.route('/collectionValue', methods=('GET',))
@verify_token
def collectionValue():
    db = get_db()
    cur = db.cursor()
    value = cur.execute('SELECT SUM(market_value) FROM collection').fetchone()[0]
    return jsonify({'status': 'success','value': value}),200

@bp.route('/addToSingles', methods=('POST',))
@verify_token
def addToSingles():
    if request.method == 'POST':
        db = get_db()
        auction_id = 1
        data = request.get_json()

        for card in data[1:]:
            db.execute('INSERT INTO cards (card_name, card_num, condition, card_price, market_value, auction_id)'
                    'VALUES (?, ?, ?, ?, ?, ?)',
                    (
                        card.get('cardName'),
                        card.get('cardNum'),
                        card.get('condition'),
                        card.get('buyPrice'),
                        card.get('marketValue'),
                        auction_id
                    )
            )
        db.commit()
    return jsonify({'status': 'success'}), 201

@bp.route('/updateAuction/<int:auction_id>', methods=('PATCH',))
@verify_token
def updateAuction(auction_id):
    db = get_db()
    data = request.get_json()
    value = data.get('value')
    field = data.get('field')
    
    ALLOWED_FIELDS = {
        "auction_name": "auction_name",
        "auction_price": "auction_price",
        "date_created": "date_created",
        }

    if field not in ALLOWED_FIELDS:
        logger.warning('Invalid field | auction_id : %s', auction_id)
        return jsonify({'status': 'error', 'message': 'Invalid field'})
    column = ALLOWED_FIELDS[field]
    db.execute(f'UPDATE auctions SET {column} = ? WHERE id = ?', (value, auction_id))
    db.commit()
    return jsonify({'status': 'success'}), 200

@bp.route('/updatePaymentMethod/<int:auction_id>', methods=('PATCH',))
@verify_token
def updatePaymentMethod(auction_id):
    db = get_db()
    data = request.get_json()
    payments = data.get('payments')  # Expecting array of {type, amount} objects
    
    # Validate and sanitize input
    is_valid, sanitized_payments, error_msg = validate_and_sanitize_payments(payments)
    if not is_valid:
        return jsonify({'status': 'error', 'message': f'{error_msg}, Error code: Ax09'}), 400
    
    # Store as JSON string
    payment_method_json = json.dumps(sanitized_payments)
    db.execute('UPDATE auctions SET payment_method = ? WHERE id = ?', (payment_method_json, auction_id))
    db.commit()

    return jsonify({'status': 'success'}), 200



@bp.route('/recalculateCardPrices/<int:auction_id>/<string:new_auction_price>', methods=('POST',))
@verify_token
def recalculateCardPrices(auction_id, new_auction_price):
    db = get_db()
    new_auction_price = float(new_auction_price)

    for item_type, unit_price in CONSTANTS.BULK_ITEM_UNIT_PRICES.items():
        quantity = db.execute(
            'SELECT quantity FROM bulk_items WHERE auction_id = ? AND item_type = ?',
            (auction_id, item_type)
        ).fetchone()
        if quantity:
            new_auction_price -= (quantity[0] * unit_price)
    # Get unsold cards from the auction
    cards = db.execute(
        'SELECT c.id, c.market_value, si.card_id '
        'FROM cards c '
        'LEFT JOIN sale_items si ON c.id = si.card_id '
        'WHERE c.auction_id = ?',
        (auction_id,)
    ).fetchall()

    # Get unsealed items from the auction
    sealed_items = db.execute(
        'SELECT s.id, s.market_value, s.sale_id '
        'FROM sealed s '
        'WHERE s.auction_id = ?',
        (auction_id,)
    ).fetchall()

    if not cards and not sealed_items:
        logger.warning('No unsold cards or sealed items found | auction_id: %s', auction_id)
        return jsonify({'status': 'error', 'message': 'No unsold cards or sealed items found, Error code: Ax10'}), 400

    for card in cards:
        if card["card_id"] is not None:
            return jsonify({'status': 'error', 'message': 'Some cards have already been sold, Error code: Ax11'}), 400

    # Check if any sealed items have been sold
    for item in sealed_items:
        if item["sale_id"] is not None:
            return jsonify({'status': 'error', 'message': 'Some sealed items have already been sold, Error code: Ax12'}), 400

    # Calculate total market value of unsold cards and sealed items
    total_market_value = sum(card['market_value'] or 0 for card in cards) + \
                         sum(item['market_value'] or 0 for item in sealed_items)
    
    if total_market_value == 0:
        logger.warning('Market value is 0 | auction_id: %s', auction_id)
        return jsonify({'status': 'error', 'message': 'Total market value is zero, Error code: Ax13'}), 400

    priceDiff = total_market_value - new_auction_price

    # Update each card proportionally
    try:
        for card in cards:
            if card['market_value'] is not None and card['market_value'] > 0:
                discount = (card['market_value'] / total_market_value) * priceDiff
                new_price = round(card['market_value'] - discount, 2)
                db.execute('UPDATE cards SET card_price = ? WHERE id = ?', (new_price, card['id']))

        # Update sealed items proportionally
        for item in sealed_items:
            if item['market_value'] is not None and item['market_value'] > 0:
                discount = (item['market_value'] / total_market_value) * priceDiff
                new_price = round(item['market_value'] - discount, 2)
                db.execute('UPDATE sealed SET price = ? WHERE id = ?', (new_price, item['id']))
    except Exception as e:
        db.rollback()
        logger.exception(
            'Database error while adjusting cards | auction_id: %s | error: %s',
            auction_id,
            e,
        )
        raise
    
    db.commit()
    return jsonify({'status': 'success'}), 200

@bp.route('/groupUnnamed', methods=('GET',))
@verify_token
def groupUnnamed():
    if request.method == 'GET':
        db = get_db()
        cursor = db.cursor()
        id = cursor.execute("SELECT id FROM auctions WHERE auction_name IS NULL ORDER BY id ASC LIMIT 1").fetchone()[0]
        db.execute("UPDATE cards SET auction_id = ? FROM cards c JOIN auctions a ON c.auction_id = a.id WHERE a.auction_name IS NULL", (id,))
        db.execute("UPDATE auctions SET auction_price = (SELECT SUM(market_value) FROM cards WHERE auction_id = ?) WHERE id = ?", (id, id, ))
        db.commit()
        return jsonify({'status': 'success'}), 200

#Gets rows of CM table using chrome extension and save them to the datasabe
@bp.route('/CardMarketTable', methods=('POST',))
@csrf.exempt
@require_api_token
def cardMarketTable():
    origin = request.headers.get("Origin", "")
    if origin != 'chrome-extension://'+ os.getenv('CHROME_EXTENSION_ID'):
        abort(403)
    if request.method == 'POST':
        db = get_db()
        data = request.get_json()
        cards = data.get('cards')
        sealed = data.get('sealed')
        date = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
        auction = {
            'name': None,
            'buy': None,
            'date': date
        }

        auction["buy"] = sum((float(card.get('marketValue', 0)) * 0.8) for card in cards)
        auction["buy"] = round(auction["buy"], 2)
        try:
            cursor = db.execute(
                'INSERT INTO auctions (auction_name, auction_price, date_created) VALUES (?, ?, ?)',
                (auction['name'], auction['buy'], auction['date'])
            )
            auction_id = cursor.lastrowid
            cardsToInsert = []
            
            for card in cards:
                # Safely convert count to integer
                try:
                    count = int(card.get('count', 1))
                except (ValueError, TypeError):
                    count = 1
                    
                for _ in range(count):
                    marketValue = card.get('marketValue', 0)
                    marketValue = float(marketValue) if marketValue is not None else None

                    if marketValue:
                        buyPrice = round(marketValue * 0.80, 2)
                    else:
                        buyPrice = 0

                    cardsToInsert.append((
                        card.get('name', None),
                        card.get('num', None),
                        card.get('condition', None),
                        buyPrice,
                        marketValue,
                        auction_id
                    ))
            
            # Execute the insert ONCE after building the full list
            db.executemany(
                'INSERT INTO cards (card_name, card_num, condition, card_price, market_value, auction_id) VALUES (?, ?, ?, ?, ?, ?)',
                cardsToInsert
            )            

            sealedToInsert = []
            for item in sealed:
                try:
                    count = int(card.get('count', 1))
                except (ValueError, TypeError):
                    count = 1
                for _ in range(count):
                    marketValue = item.get('marketValue', 0)
                    marketValue = float(marketValue) if marketValue is not None else None

                    if marketValue:
                        buyPrice = round(marketValue * 0.80, 2)
                    else:
                        buyPrice = 0

                    sealedToInsert.append((
                        item.get('name', None),
                        buyPrice,
                        marketValue,
                        auction_id
                    ))

            db.executemany(
                'INSERT INTO sealed (name, price, market_value, auction_id) VALUES (?, ?, ?, ?)', sealedToInsert
            )

            db.commit()
            logger.info('Cards successfully imported | auction_id: %s', auction_id)
            return jsonify({'status': 'success'}), 201

        except Exception as e:
            print("DB error:", e)
            logger.exception('DB error')
            return jsonify({'status': 'error', 'message': 'Error code: Ax15'}), 500

@bp.route('/cardMarketOrder', methods=('POST',))
@csrf.exempt
@limiter.limit('10 per minute')
@require_api_token
def cardMarketOrder():
    origin = request.headers.get("Origin", "")
    if origin != 'chrome-extension://'+ os.getenv('CHROME_EXTENSION_ID'):
        abort(403)
    data = request.get_json()
    db = get_db()
    shipping_info = data['shipping_info']
    cards = data['cards']

    if cards:
        try:
            for card in cards:
                
                try:
                    count = int(card.get('count', 1))
                except (ValueError, TypeError):
                    print('failed to get count')
                    count = 1
            
                rows = db.execute("SELECT c.id FROM cards c LEFT JOIN sale_items si ON c.id = si.card_id WHERE lower(c.card_name) = ? AND lower(c.card_num) = ? and upper(c.condition) = ? AND si.sale_id IS NULL",(card['name'].lower(), card['num'].lower(), card['condition'].upper())).fetchmany(count)
        
                ids = [row[0] for row in rows]
                ids += [None] * (count - len(ids))
                card['cardId'] = ids
        
        except Exception as e:
            print('There was an error while getting card ids')
            logger.exception('cardMarketOrder failed to get card ids')
            return jsonify({'status': 'error', 'message' : 'Failed to match cards to card ids, Error code: Ax16'}), 400


    sealed = data['sealed']
    if sealed:
        try:
            for item in sealed:
                try:
                    count = int(item.get('count',1))
                except:
                    count = 1


                rows  = db.execute('SELECT id FROM WHERE lower(name) = ? AND sale_id IS NULL',(item['name'].lower(),)).fetchmany(count)
                ids = [row[0] for row in rows]
                if len(ids) > 0:
                  item['id'] = ids
        except:
            print("There was an error while getting sealed ids")
            logger.exception('cardMarketOrder failed to get sealed ids')
            return jsonify({'status' : 'error', 'message': 'There was an error while getting sealed ids, Error code: Ax17'})

    shipping_info['paybackDate'] = datetime.date.today().strftime("%d/%m/%Y")
    orderInfo = {
            "shipping_info" : shipping_info,
            "cards" : cards,
            "sealed" : sealed
            }
    global latest
    print(orderInfo)
    latest = orderInfo
    logger.info('Order succcessfully extracted')
    return jsonify({'status': 'success'}), 200

@bp.route('/getLatest', methods=('GET',))
@verify_token
def getLatest():
    global latest
    last = latest
    latest = None
    if last is not None:
        return jsonify({'status': 'success', 'message': last}), 200
    else:
        return jsonify({'status': 'empty'}), 200

def createDicts(lines):
    zipped = list(zip(*[line.split(';') for line in lines]))

    dictsNum = len(zipped[0]) - 1
    dicts = [{} for _ in range(dictsNum)]

    for row in zipped:
        key = row[0].strip()
        for i in range(dictsNum):
            dicts[i][key] = row[i + 1].strip()

    return dicts
    
def getImportantCollums(cards, columns):
    data = []
    for d in cards:
        order_id = list(d.values())[columns['Order ID']].upper()
        count = int(list(d.values())[columns['Product ID'] + 1])
        name = list(d.values())[columns['Product ID'] + 2].upper()
        number = list(d.values())[columns['Collector Number']].upper()
        condition = list(d.values())[columns['Condition']]
        #print("Condition:", condition)
        condition = conditionDict.get(condition)
        #print("Mapped Condition:", condition)
        price = float(list(d.values())[columns['Expansion'] + 1])
        language = list(d.values())[columns['Language']]
        expansion = list(d.values())[columns['Expansion']]
        if language:
            expansion = all_pokemon_sets.get(expansion)
        else:
            expansion = None
        #print("Expansion:", expansion)
        #print("Number:", number)
        if expansion != None and number != None:
            card_num = expansion +" "+ number
        elif expansion == None:
            card_num = number
        else:
            card_num = expansion
        for _ in range(count):
            filteredRow = [order_id, name, condition, price, card_num]
            temp = zip(dictKeys, filteredRow)
            data.append(dict(temp))
    return data

def updateOneCard(db, name, num, condition, sellPrice):
    #print(name, num, condition, sellPrice)
    cardId = db.execute(
        "SELECT c.id FROM cards c "
        "LEFT JOIN sale_items si ON c.id = si.card_id "
        "WHERE c.card_name = ? AND c.card_num LIKE ? AND c.condition = ? AND si.card_id IS NULL "
        "LIMIT 1", (name, f'%{num}', condition)).fetchone()
    if cardId:
        date = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"
        card = db.execute("SELECT auction_id, card_price FROM cards WHERE id = ?", (cardId['id'],)).fetchone()
        
        # Create a sale for this card
        invoice_number = f"CSV-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{cardId['id']}"
        db.execute(
            "INSERT INTO sales (invoice_number, sale_date, total_amount) VALUES (?, ?, ?)",
            (invoice_number, date, sellPrice)
        )
        sale_id = db.cursor().lastrowid
        
        # Add sale item
        db.execute(
            "INSERT INTO sale_items (sale_id, card_id, sell_price, sold_cm) VALUES (?, ?, ?, ?)",
            (sale_id, cardId['id'], sellPrice, 1)
        )
        db.commit()
        return
    else:
        db.commit()
        return
    
def allowedFile(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in "csv"

@bp.route('/importSoldCSV', methods=('POST',))
@verify_token
def importSoldCSV():
    if request.method == 'POST':
        # Use the same folder as the database
        if os.getenv("FLASK_ENV") == "prod":
            data_dir = os.getenv("DATA_DIR", current_app.instance_path)
            os.makedirs(data_dir, exist_ok=True)
            check_file_path = os.path.join(data_dir, 'checkFile.csv')
        else:
            # Running in development
            check_file_path = os.path.join(current_app.instance_path, 'checkFile.csv')
            os.makedirs(os.path.dirname(check_file_path), exist_ok=True)
        
        if 'csv-upload' not in request.files:
            return jsonify({'status': 'missing'}), 400
        
        file = request.files['csv-upload']
        if file.filename == '':
            return jsonify({'status': 'file'}), 400
        if not allowedFile(file.filename):
            return jsonify({'status': 'extension'}), 400
        
        lines = []
        existingOrderID = set()

        CHECK_PATH = check_file_path
        try:
            # Read existing order IDs
            if os.path.exists(CHECK_PATH):
                with open(CHECK_PATH, 'r', encoding='utf-8') as checkFile:
                    existingLines = checkFile.read().splitlines()
            else:
                existingLines = []

            # Process new file
            for line in file.stream:
                try:
                    decoded = line.decode("utf-8").strip()
                    if decoded == "":
                        continue
                    
                    # Ensure we have enough columns
                    columns = decoded.split(';')
                    if len(columns) <= 12:
                        continue
                        
                    orderId = columns[12].strip()
                    if any(orderId in existingLine for existingLine in existingLines):
                        continue
                    lines.append(decoded)
                    existingOrderID.add(orderId)
                except UnicodeDecodeError:
                    print(f"Warning: Skipping line due to encoding issues")
                    continue

            # Remove header if present
            if "Order ID" in existingOrderID:
                existingOrderID.remove("Order ID")
            
            if not lines:
                return jsonify({'status': 'duplicate'}), 400

            # Process cards
            cards = createDicts(lines)
            try:
                columns = {name: key for key, name in enumerate(cards[0].keys())}
            except (IndexError, KeyError) as e:
                print(f"Error processing CSV structure: {e}")
                return jsonify({'status': 'invalid_format'}), 400

            dataList = getImportantCollums(cards, columns)

            # Update database
            db = get_db()
            for item in dataList:
                updateOneCard(db, item.get('Name'), item.get('Card Number'), item.get('Condition'), item.get('Price'))

            # Save updated check file
            existingOrderID = sorted(existingOrderID, key=int)
            with open(CHECK_PATH, 'w', encoding='utf-8') as checkFile:
                for orderId in existingOrderID:
                    checkFile.write(orderId + '\n')

        except Exception as e:
            logger.exception('Failed to proces CSV file | reason: %s', e)
            print(f"Error processing CSV file: {e}")
            return jsonify({'status': 'error', 'message': f'{str(e)}, Error code: Ax19'}), 500


    return jsonify({'status': 'success'}), 201

@bp.route('/searchCard', methods=('POST',))
@verify_token
def search():
    if request.method == 'POST':
        card = request.get_json()
        query = card.get("query", "").strip()
        cart_ids = card.get('cartIds', [])
        # Split search query into individual words
        search_terms = query.split()
        
        # Separate cart IDs into cards and sealed items
        card_cart_ids = []
        sealed_cart_ids = []
        for cart_id in cart_ids:
            if isinstance(cart_id, str) and cart_id.startswith('s'):
                # Remove 's' prefix and convert to int
                sealed_cart_ids.append(int(cart_id[1:]))
            else:
                card_cart_ids.append(cart_id)
        
        # Build WHERE clause for CARDS (alias 'c')
        card_where_conditions = []
        card_params = []
        for term in search_terms:
            card_where_conditions.append(
                "UPPER(COALESCE(c.card_name, '') || ' ' || COALESCE(c.card_num, '')) LIKE UPPER(?)"
            )
            card_params.append(f'%{term}%')
        
        #TODO cant this be a group by conditions?
        card_where_clause = " AND ".join(card_where_conditions) if card_where_conditions else "1=1"
        
        # Add card cart exclusion
        if card_cart_ids:
            placeholders = ",".join(["?"] * len(card_cart_ids))
            card_where_clause += f" AND c.id NOT IN ({placeholders})"
            card_params.extend(card_cart_ids)
        
        # Build WHERE clause for SEALED items (alias 's')
        sealed_where_conditions = []
        sealed_params = []
        for term in search_terms:
            sealed_where_conditions.append("UPPER(COALESCE(s.name, '')) LIKE UPPER(?)")
            sealed_params.append(f'%{term}%')
        
        sealed_where_clause = " AND ".join(sealed_where_conditions) if sealed_where_conditions else "1=1"
        
        # Add sealed cart exclusion
        if sealed_cart_ids:
            placeholders = ",".join(["?"] * len(sealed_cart_ids))
            sealed_where_clause += f" AND s.id NOT IN ({placeholders})"
            sealed_params.extend(sealed_cart_ids)
        
        db = get_db()
        
        # Search cards
        card_matches = db.execute(
            f"SELECT c.card_name, c.card_num, c.condition, c.market_value, c.id, c.auction_id,COUNT(*) as available_count, a.auction_name FROM cards c "
            "JOIN auctions a ON c.auction_id = a.id "
            "LEFT JOIN sale_items si ON c.id = si.card_id "
            f"WHERE ({card_where_clause}) AND si.card_id IS NULL "
            "GROUP BY UPPER(c.card_name), UPPER(c.card_num), UPPER(c.condition) ORDER BY c.id ASC LIMIT 8",
            card_params
        ).fetchall()
        
        # Search sealed items
        sealed_matches = db.execute(
            f"SELECT 's' || s.id as sid, s.name, s.market_value, s.auction_id,COUNT(*) as available_count, a.auction_name FROM sealed s "
            "LEFT JOIN auctions a ON s.auction_id = a.id "
            f"WHERE ({sealed_where_clause}) AND s.sale_id IS NULL "
            f"GROUP BY UPPER(s.name) ORDER BY s.id ASC LIMIT 8",
            sealed_params
        ).fetchall()
        
        # Combine results and convert to dicts
        all_matches = [dict(m) for m in card_matches] + [dict(m) for m in sealed_matches]
        
        # Take top 8 results (interleaved by ID-based relevance)
        final_matches = all_matches[:8]

        if not final_matches:
            return jsonify({'status': 'success','value': None}),200
        else:
            return jsonify({'status': 'success','value': final_matches}),200


@bp.route('/getCardIds', methods=('POST',))
@verify_token
def getCardIds():
    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'Invalid input, Error code: Ax20'}), 400

        card_name = data.get('card_name')
        card_num = data.get('card_num')
        condition = data.get('condition')
        exclude_ids = data.get('exclude_ids', [])

        if not card_name or not condition:
            return jsonify({'status': 'error', 'message': 'Missing required fields, Error code: Ax21'}), 400

        db = get_db()

        if card_num is None:
            query = ('SELECT c.id FROM cards c '
                     'LEFT JOIN sale_items si ON c.id = si.card_id '
                     'WHERE c.card_name = ? '
                     'AND c.card_num IS NULL '
                     'AND c.condition = ? '
                     'AND si.card_id IS NULL')
            params = [card_name, condition]
        else:
            query = ('SELECT c.id FROM cards c '
                     'LEFT JOIN sale_items si ON c.id = si.card_id '
                     'WHERE c.card_name = ? '
                     'AND c.card_num = ? '
                     'AND c.condition = ? '
                     'AND si.card_id IS NULL')
            params = [card_name, card_num, condition]

        if exclude_ids:
            placeholders = ','.join('?' for _ in exclude_ids)
            query += f' AND c.id NOT IN ({placeholders})'
            params.extend(exclude_ids)

        query += ' ORDER BY c.id ASC'

        cardIds = db.execute(query, params).fetchall()
        ids = [dict(row)['id'] for row in cardIds]
        return jsonify({'status': 'success', 'card_ids': ids}), 200

@bp.route('/createSale/<string:kind>', methods=('POST',))
@limiter.limit("5 per minute")
@verify_token
def invoice(kind):
    if request.method == 'POST':
        #TODO add asymetric decryption
        cartContent = request.get_json()

        payment_data, valid, err = None, False, None
        payment_methods_input = cartContent.get('paymentMethods') or []

        if payment_methods_input:
            valid, payment_data, err = validate_and_sanitize_payments(payment_methods_input)
        elif cartContent.get('paymentMethod'):
            # Backwards compatibility - convert single payment method to array
            payment_data = [{'type': cartContent.get('paymentMethod'), 'amount': 0}]
            valid = True
        else:
            err = 'No payment method provided'

        if err != None:
            logger.error('Payment validation failed | %s', err)
            return jsonify({'status': 'error', 'message': f'There was an error while validating payments {err}, Error code: Ax22'}), 400
        if not valid:
            return jsonify({'status': 'error', 'message': 'Invalid payment data, Error code: Ax23'}), 400

        saleInput = SaleInput(
            reciever=cartContent['recieverInfo'],
            cards=cartContent.get('cards') or [],
            sealed=cartContent.get('sealed') or [],
            bulk=cartContent.get('bulkItem'),
            holo=cartContent.get('holoItem'),
            ex=cartContent.get('exItem'),
            shipping=cartContent.get('shipping'),
            payments=payment_data or [],
        )
        # Validate inventory before processing
        db = get_db()
        
        if kind == 'invoice': 

            try:
                saleResult = SaleService(db,InvoiceReceiptService()).process_sale(saleInput)
                receipt = saleResult.receipt.raw
                response = send_file(
                        BytesIO(receipt['bytes']),
                        download_name=receipt['filename'],
                        as_attachment=True,
                        mimetype='application/pdf'
                        )
                db.commit()
                logger.info('Invoice created succesfully | %s ', saleResult.sale_id)
                return response 
                

            except Exception as e:
                db.rollback()
                logger.exception('Failed to create invoice | %s', e)
                return jsonify({'status': 'error', 'message': f'There was an error {e}, Error code: Ax24'}), 400

        elif kind == 'sales_invoice':

            try:
                saleResult = SaleService(db, EKasaReceiptService()).process_sale(saleInput)
                receipt = saleResult.receipt.raw
                response = send_file(
                        BytesIO(receipt['bytes']),
                        download_name=receipt['filename'],
                        as_attachment=True,
                        mimetype='application/pdf'
                        )
                db.commit()
                logger.info('Invoice created succesfully | %s ', saleResult.sale_id)
                return response 

            except Exception as e:
                db.rollback()
                logger.exception('Failed to create sale | %s', e)
                return jsonify({'status': 'error', 'message': f'There was an error {e}, Error code: Ax25'}), 400
        
        return jsonify({'status': 'error', 'message': 'Invalid kind of request, Error code: Ax26'}), 400
