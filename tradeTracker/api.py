from flask import request, Blueprint, jsonify, current_app, abort
from tradeTracker.db import get_db
import datetime
import logging
from . import csrf, limiter
from tradeTracker.services.cfAuth import require_api_token
from tradeTracker import actions
from tradeTracker import CONSTANTS


bp = Blueprint('api', __name__)
logger = logging.getLogger(__name__)


def _positive_item_count(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count > 0 else None


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
        languages = [
            str(item.get('language', 'en')).strip().lower()
            for item in [*cards, *sealed]
        ]
        if any(language not in CONSTANTS.ALLOWED_LANGUAGES for language in languages):
            return jsonify({'status': 'error', 'message': 'Invalid language code, Error code: Ax27'}), 400
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
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
                count = _positive_item_count(card.get('count', 1))
                if count is None:
                    db.rollback()
                    return jsonify({'status': 'error', 'message': 'Invalid item count'}), 400
                    
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
                        str(card.get('language', 'en')).strip().lower(),
                        buyPrice,
                        marketValue,
                        auction_id
                    ))
        
            # Execute the insert ONCE after building the full list
            db.executemany(
                'INSERT INTO cards (card_name, normalized_name, card_num, condition, language, card_price, market_value, auction_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                cardsToInsert
            )

            sealedToInsert = []
            for item in sealed:
                count = _positive_item_count(item.get('count', 1))
                if count is None:
                    db.rollback()
                    return jsonify({'status': 'error', 'message': 'Invalid item count'}), 400
                marketValue = item.get('marketValue', 0)
                marketValue = float(marketValue) if marketValue is not None else None

                if marketValue:
                    buyPrice = round(marketValue * 0.80, 2)
                else:
                    buyPrice = 0

                sealedToInsert.append((
                    item.get('name', None),
                    actions.normalize(item.get('name')),
                    str(item.get('language', 'en')).strip().lower(),
                    count,
                    buyPrice,
                    marketValue,
                    date,
                    auction_id
                ))

            db.executemany(
                'INSERT INTO sealed (name, normalized_name, language, quantity, price, market_value, date, auction_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', sealedToInsert
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
                count = _positive_item_count(card.get('count', 1))
                if count is None:
                    return jsonify({'status': 'error', 'message': 'Invalid item count'}), 400
            
                rows = db.execute("SELECT c.id FROM cards c LEFT JOIN sale_items si ON c.id = si.card_id "
                                  "WHERE lower(c.card_name) = ? AND lower(c.card_num) = ? and upper(c.condition) = ? AND c.language = ? AND si.sale_id IS NULL",
                                  (card['name'].lower(), card['num'].lower(), card['condition'].upper(), card.get('language', 'en').lower())).fetchmany(count)
        
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
                count = _positive_item_count(item.get('count', 1))
                if count is None:
                    return jsonify({'status': 'error', 'message': 'Invalid item count'}), 400

                language = item.get('language', 'en').lower()
                if language not in CONSTANTS.ALLOWED_LANGUAGES:
                    return jsonify({'status': 'error', 'message': 'Invalid language code, Error code: Ax27'}), 400

                available = db.execute(
                    'SELECT COALESCE(SUM(quantity), 0) FROM sealed WHERE lower(name) = ? AND language = ? AND sale_id IS NULL AND opened = 0',
                    (item['name'].lower(), language)
                ).fetchone()[0]
                first = db.execute(
                    'SELECT id FROM sealed WHERE lower(name) = ? AND language = ? AND sale_id IS NULL AND opened = 0 ORDER BY id ASC LIMIT 1',
                    (item['name'].lower(), language)
                ).fetchone()
                item['language'] = language
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
    actions.latest = orderInfo
    logger.info('Order succcessfully extracted')
    return jsonify({'status': 'success'}), 200

