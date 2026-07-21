import os
import sys
import tempfile
import unittest
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tradeTracker import create_app
from tradeTracker.actions import resolve_cardmarket_id
from tradeTracker.db import get_db, init_db


class CardMarketIdResolutionTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
            'WTF_CSRF_ENABLED': False,
        })
        with self.app.app_context():
            get_db().executescript('DROP TABLE IF EXISTS barter;')
            init_db()
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _add_external(self, cardmarket_id, name, card_num):
        db = get_db()
        db.execute(
            'INSERT INTO external (cardmarketId, card_name, card_num, expansion) VALUES (?, ?, ?, ?)',
            (cardmarket_id, name, card_num, 'Test Set'),
        )
        db.commit()

    def test_payload_id_takes_precedence_over_external_match(self):
        with self.app.app_context():
            self._add_external('100', 'Pikachu', 'SVI 58')
            cardmarket_id = resolve_cardmarket_id(
                get_db(),
                {'cardName': 'Pikachu', 'cardNum': 'SVI 58', 'cardmarketId': '200'},
                'cardName',
                'cardNum',
            )
            self.assertEqual(cardmarket_id, '200')

    def test_external_match_is_used_when_payload_has_no_id(self):
        with self.app.app_context():
            self._add_external('100', 'Pikachu', 'SVI 58')
            cardmarket_id = resolve_cardmarket_id(
                get_db(),
                {'cardName': 'pikachu', 'cardNum': 'svi 58'},
                'cardName',
                'cardNum',
            )
            self.assertEqual(cardmarket_id, '100')

    def test_missing_or_ambiguous_external_match_returns_none_and_logs(self):
        with self.app.app_context():
            db = get_db()
            with self.assertLogs('tradeTracker.actions', level='WARNING'):
                self.assertIsNone(resolve_cardmarket_id(
                    db, {'cardName': 'Missing', 'cardNum': '1'}, 'cardName', 'cardNum'
                ))

            self._add_external('100', 'Pikachu', 'SVI 58')
            self._add_external('101', 'Pikachu', 'SVI 58')
            with self.assertLogs('tradeTracker.actions', level='WARNING'):
                self.assertIsNone(resolve_cardmarket_id(
                    db, {'cardName': 'Pikachu', 'cardNum': 'SVI 58'}, 'cardName', 'cardNum'
                ))

    def test_manual_card_and_sealed_routes_use_external_lookup(self):
        with self.app.app_context():
            db = get_db()
            db.execute('INSERT INTO auctions (id, auction_name) VALUES (2, "Existing")')
            self._add_external('100', 'Auction Card', '1')
            self._add_external('101', 'Singles Card', '2')
            self._add_external('102', 'Existing Card', '3')
            self._add_external('103', 'Existing Sealed', '')
            self._add_external('104', 'Standalone Sealed', '')

        response = self.client.post('/add', data=json.dumps([
            {'name': 'Auction', 'buy': 1, 'date': '2026-01-01'},
            {'cardName': 'Auction Card', 'cardNum': '1', 'condition': 'NM', 'buyPrice': 1, 'marketValue': 2},
        ]), content_type='application/json', base_url='https://localhost')
        self.assertEqual(response.status_code, 201, response.data)

        response = self.client.post('/addToSingles', data=json.dumps([
            {},
            {'cardName': 'Singles Card', 'cardNum': '2', 'condition': 'NM', 'buyPrice': 1, 'marketValue': 2},
        ]), content_type='application/json', base_url='https://localhost')
        self.assertEqual(response.status_code, 201, response.data)

        response = self.client.post('/addToExistingAuction/2', data=json.dumps({
            'cards': [{'cardName': 'Existing Card', 'cardNum': '3', 'condition': 'NM', 'buyPrice': 1, 'marketValue': 2}],
            'sealed': [{'name': 'Existing Sealed', 'quantity': 1, 'price': '1', 'market_value': '2', 'date': '2026-01-01'}],
        }), content_type='application/json', base_url='https://localhost')
        self.assertEqual(response.status_code, 201, response.data)

        response = self.client.post('/addSealed', data=json.dumps([
            {'name': 'Standalone Sealed', 'price': '1', 'market_value': '2', 'dateAdded': '2026-01-01'},
        ]), content_type='application/json', base_url='https://localhost')
        self.assertEqual(response.status_code, 200, response.data)

        with self.app.app_context():
            db = get_db()
            card_ids = [row['cardMarketID'] for row in db.execute(
                'SELECT cardMarketID FROM cards ORDER BY id'
            ).fetchall()]
            sealed_ids = [row['cardMarketID'] for row in db.execute(
                'SELECT cardMarketID FROM sealed ORDER BY id'
            ).fetchall()]
            self.assertEqual(card_ids, ['100', '101', '102'])
            self.assertEqual(sealed_ids, ['103', '104'])

    def test_cardmarket_import_uses_payload_ids_and_external_fallback(self):
        with self.app.app_context():
            self._add_external('100', 'Lookup Card', '1')
            self._add_external('101', 'Lookup Sealed', '')

        token = os.environ['CHROME_EXTENSION_API_TOKEN']
        response = self.client.post('/CardMarketTable', data=json.dumps({
            'cards': [
                {'name': 'Lookup Card', 'num': '1', 'condition': 'NM', 'marketValue': 2},
                {'name': 'Payload Card', 'num': '2', 'condition': 'NM', 'marketValue': 2, 'cardmarketId': '200'},
            ],
            'sealed': [
                {'name': 'Lookup Sealed', 'count': 1, 'marketValue': 2},
                {'name': 'Payload Sealed', 'count': 1, 'marketValue': 2, 'cardmarketId': '201'},
            ],
        }), content_type='application/json', headers={'Authorization': f'Bearer {token}'}, base_url='https://localhost')
        self.assertEqual(response.status_code, 201, response.data)

        with self.app.app_context():
            db = get_db()
            card_ids = [row['cardMarketID'] for row in db.execute(
                'SELECT cardMarketID FROM cards ORDER BY id'
            ).fetchall()]
            sealed_ids = [row['cardMarketID'] for row in db.execute(
                'SELECT cardMarketID FROM sealed ORDER BY id'
            ).fetchall()]
            self.assertEqual(card_ids, ['100', '200'])
            self.assertEqual(sealed_ids, ['101', '201'])


if __name__ == '__main__':
    unittest.main()
