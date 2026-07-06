from flask import request, Blueprint, jsonify, current_app, abort
from tradeTracker.db import get_db
import datetime
import logging
from . import csrf, limiter
from tradeTracker.services.cfAuth import require_api_token
from tradeTracker import actions


bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)


#Gets rows of CM table using chrome extension and save them to the datasabe
@bp.route('/CardMarketTable', methods=('POST',))
@csrf.exempt
@require_api_token
def cardMarketTable():
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
                        actions.normalize(card.get('name')),
                        card.get('num', None),
                        card.get('condition', None),
                        buyPrice,
                        marketValue,
                        auction_id
                    ))
        
            # Execute the insert ONCE after building the full list
            db.executemany(
                'INSERT INTO cards (card_name, normalized_name, card_num, condition, card_price, market_value, auction_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
                cardsToInsert
            )

            sealedToInsert = []
            for item in sealed:
                marketValue = item.get('marketValue', 0)
                marketValue = float(marketValue) if marketValue is not None else None

                if marketValue:
                    buyPrice = round(marketValue * 0.80, 2)
                else:
                    buyPrice = 0

                sealedToInsert.append((
                    item.get('name', None),
                    actions.normalize(item.get('name')),
                    item.get('count'),
                    buyPrice,
                    marketValue,
                    date,
                    auction_id
                ))

            db.executemany(
                'INSERT INTO sealed (name, normalized_name, quantity, price, market_value, date, auction_id) VALUES (?, ?, ?, ?, ?, ?, ?)', sealedToInsert
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

                available = db.execute(
                    'SELECT COALESCE(SUM(quantity), 0) FROM sealed WHERE lower(name) = ? AND sale_id IS NULL',
                    (item['name'].lower(),)
                ).fetchone()[0]
                first = db.execute(
                    'SELECT id FROM sealed WHERE lower(name) = ? AND sale_id IS NULL ORDER BY id ASC LIMIT 1',
                    (item['name'].lower(),)
                ).fetchone()
                if first is not None and available > 0:
                    item['id'] = [first[0]]
                    item['quantity'] = min(count, available)
                    item['available'] = available
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
    print(orderInfo)
    actions.latest = orderInfo
    logger.info('Order succcessfully extracted')
    return jsonify({'status': 'success'}), 200

