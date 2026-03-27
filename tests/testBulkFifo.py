"""
Unit tests for bulk/holo FIFO inventory deduction system
"""
import sys
import os
import unittest
import tempfile
import json
from datetime import date

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tradeTracker import create_app
from tradeTracker.db import get_db, init_db


class BulkFIFOTestCase(unittest.TestCase):
    """Test cases for bulk/holo FIFO inventory deduction"""

    def setUp(self):
        """Set up test client and initialize database"""
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            init_db()
            self._setup_test_data()

    def tearDown(self):
        """Clean up after tests"""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _setup_test_data(self):
        """Create test auctions and bulk items"""
        db = get_db()
        
        # Create test auctions
        db.execute(
            'INSERT INTO auctions (auction_name, auction_price, auction_profit) '
            'VALUES (?, ?, ?)',
            ('Test Auction 1', 50.0, 0)
        )
        db.execute(
            'INSERT INTO auctions (auction_name, auction_price, auction_profit) '
            'VALUES (?, ?, ?)',
            ('Test Auction 2', 100.0, 0)
        )
        db.execute(
            'INSERT INTO auctions (auction_name, auction_price, auction_profit) '
            'VALUES (?, ?, ?)',
            ('Test Auction 3', 75.0, 0)
        )
        
        # Add bulk items to auctions
        # Auction 2: 5 bulk @ 0.01 each
        db.execute(
            'INSERT INTO bulk_items (auction_id, item_type, quantity, unit_price, total_price) '
            'VALUES (?, ?, ?, ?, ?)',
            (2, 'bulk', 5, 0.01, 0.05)
        )
        # Auction 3: 10 bulk @ 0.01 each
        db.execute(
            'INSERT INTO bulk_items (auction_id, item_type, quantity, unit_price, total_price) '
            'VALUES (?, ?, ?, ?, ?)',
            (3, 'bulk', 10, 0.01, 0.10)
        )
        # Auction 2: 8 holo @ 0.03 each
        db.execute(
            'INSERT INTO bulk_items (auction_id, item_type, quantity, unit_price, total_price) '
            'VALUES (?, ?, ?, ?, ?)',
            (2, 'holo', 8, 0.03, 0.24)
        )
        # Auction 3: 12 holo @ 0.03 each
        db.execute(
            'INSERT INTO bulk_items (auction_id, item_type, quantity, unit_price, total_price) '
            'VALUES (?, ?, ?, ?, ?)',
            (3, 'holo', 12, 0.03, 0.36)
        )
        
        # Update bulk_counter
        db.execute('UPDATE bulk_counter SET counter = ? WHERE counter_name = "bulk"', (15,))
        db.execute('UPDATE bulk_counter SET counter = ? WHERE counter_name = "holo"', (20,))
        
        db.commit()

    def test_check_bulk_inventory_sufficient(self):
        """Test inventory check with sufficient inventory"""
        with self.app.app_context():
            db = get_db()
            from tradeTracker.actions import _check_bulk_inventory
            
            # Test bulk: 15 available, need 10
            self.assertTrue(_check_bulk_inventory(db, 'bulk', 10))
            
            # Test holo: 20 available, need 15
            self.assertTrue(_check_bulk_inventory(db, 'holo', 15))

    def test_check_bulk_inventory_insufficient(self):
        """Test inventory check with insufficient inventory"""
        with self.app.app_context():
            db = get_db()
            from tradeTracker.actions import _check_bulk_inventory
            
            # Test bulk: 15 available, need 20
            self.assertFalse(_check_bulk_inventory(db, 'bulk', 20))
            
            # Test holo: 20 available, need 25
            self.assertFalse(_check_bulk_inventory(db, 'holo', 25))

    def test_check_bulk_inventory_exact(self):
        """Test inventory check with exact inventory"""
        with self.app.app_context():
            db = get_db()
            from tradeTracker.actions import _check_bulk_inventory
            
            # Test bulk: 15 available, need 15
            self.assertTrue(_check_bulk_inventory(db, 'bulk', 15))

    def test_fifo_deduction_single_auction(self):
        """Test FIFO deduction from single auction"""
        with self.app.app_context():
            db = get_db()
            from tradeTracker.actions import _deduct_bulk_items_fifo
            
            # Deduct 3 bulk from auction 2 (has 5)
            _deduct_bulk_items_fifo(db, 'bulk', 3)
            db.commit()
            
            # Check auction 2 now has 2 bulk
            result = db.execute(
                'SELECT quantity FROM bulk_items WHERE auction_id = 2 AND item_type = "bulk"'
            ).fetchone()
            self.assertIsNotNone(result)
            self.assertEqual(result['quantity'], 2)
            
            # Check auction 3 still has 10 bulk
            result = db.execute(
                'SELECT quantity FROM bulk_items WHERE auction_id = 3 AND item_type = "bulk"'
            ).fetchone()
            self.assertEqual(result['quantity'], 10)

    def test_fifo_deduction_complete_auction(self):
        """Test FIFO deduction that completely depletes an auction"""
        with self.app.app_context():
            db = get_db()
            from tradeTracker.actions import _deduct_bulk_items_fifo
            
            # Deduct 5 bulk (exact amount in auction 2)
            _deduct_bulk_items_fifo(db, 'bulk', 5)
            db.commit()
            
            # Check auction 2 bulk is deleted
            result = db.execute(
                'SELECT * FROM bulk_items WHERE auction_id = 2 AND item_type = "bulk"'
            ).fetchone()
            self.assertIsNone(result)
            
            # Check auction 3 still has 10 bulk
            result = db.execute(
                'SELECT quantity FROM bulk_items WHERE auction_id = 3 AND item_type = "bulk"'
            ).fetchone()
            self.assertEqual(result['quantity'], 10)

    def test_fifo_deduction_multiple_auctions(self):
        """Test FIFO deduction across multiple auctions"""
        with self.app.app_context():
            db = get_db()
            from tradeTracker.actions import _deduct_bulk_items_fifo
            
            # Deduct 7 bulk (5 from auction 2 + 2 from auction 3)
            _deduct_bulk_items_fifo(db, 'bulk', 7)
            db.commit()
            
            # Check auction 2 bulk is deleted
            result = db.execute(
                'SELECT * FROM bulk_items WHERE auction_id = 2 AND item_type = "bulk"'
            ).fetchone()
            self.assertIsNone(result)
            
            # Check auction 3 now has 8 bulk
            result = db.execute(
                'SELECT quantity FROM bulk_items WHERE auction_id = 3 AND item_type = "bulk"'
            ).fetchone()
            self.assertEqual(result['quantity'], 8)

    def test_fifo_deduction_all_inventory(self):
        """Test FIFO deduction of all available inventory"""
        with self.app.app_context():
            db = get_db()
            from tradeTracker.actions import _deduct_bulk_items_fifo
            
            # Deduct all 15 bulk
            _deduct_bulk_items_fifo(db, 'bulk', 15)
            db.commit()
            
            # Check no bulk items remain
            results = db.execute(
                'SELECT * FROM bulk_items WHERE item_type = "bulk"'
            ).fetchall()
            self.assertEqual(len(results), 0)

    def test_fifo_deduction_holo_items(self):
        """Test FIFO deduction for holo items"""
        with self.app.app_context():
            db = get_db()
            from tradeTracker.actions import _deduct_bulk_items_fifo
            
            # Deduct 10 holo (8 from auction 2 + 2 from auction 3)
            _deduct_bulk_items_fifo(db, 'holo', 10)
            db.commit()
            
            # Check auction 2 holo is deleted
            result = db.execute(
                'SELECT * FROM bulk_items WHERE auction_id = 2 AND item_type = "holo"'
            ).fetchone()
            self.assertIsNone(result)
            
            # Check auction 3 now has 10 holo
            result = db.execute(
                'SELECT quantity FROM bulk_items WHERE auction_id = 3 AND item_type = "holo"'
            ).fetchone()
            self.assertEqual(result['quantity'], 10)

    def test_invoice_insufficient_bulk_inventory(self):
        """Test invoice endpoint rejects insufficient bulk inventory"""
        # Create a mock invoice request with insufficient bulk
        payload = {
            'cards': [{'cardId': 1, 'marketValue': '5.00'}],
            'bulkItem': {
                'counter_name': 'bulk',
                'quantity': 20,  # Only 15 available
                'unit_price': 0.01,
                'sell_price': 0.20,
                'buy_price': 0.01
            },
            'recieverInfo': {
                'paymentMethod': 'Hotovosť',
                'nameAndSurname': 'Test User',
                'address': 'Test Address',
                'city': 'Test City',
                'paybackDate': date.today().isoformat(),
                'total': 5.20
            }
        }
        
        response = self.client.post(
            '/invoice/0',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Insufficient bulk inventory', data['message'])

    def test_invoice_insufficient_holo_inventory(self):
        """Test invoice endpoint rejects insufficient holo inventory"""
        payload = {
            'cards': [{'cardId': 1, 'marketValue': '5.00'}],
            'holoItem': {
                'counter_name': 'holo',
                'quantity': 25,  # Only 20 available
                'unit_price': 0.03,
                'sell_price': 0.75,
                'buy_price': 0.03
            },
            'recieverInfo': {
                'paymentMethod': 'Hotovosť',
                'nameAndSurname': 'Test User',
                'address': 'Test Address',
                'city': 'Test City',
                'paybackDate': date.today().isoformat(),
                'total': 5.75
            }
        }
        
        response = self.client.post(
            '/invoice/0',
            data=json.dumps(payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'error')
        self.assertIn('Insufficient holo inventory', data['message'])

    def test_delete_auction_removes_bulk_items(self):
        """Test that deleting an auction also deletes its bulk items"""
        with self.app.app_context():
            db = get_db()
            
            # Verify auction 2 has bulk items
            result = db.execute(
                'SELECT COUNT(*) as count FROM bulk_items WHERE auction_id = 2'
            ).fetchone()
            self.assertEqual(result['count'], 2)  # bulk and holo
            
            # Delete auction 2
            response = self.client.delete('/deleteAuction/2')
            self.assertEqual(response.status_code, 200)
            
            # Verify bulk items are deleted
            result = db.execute(
                'SELECT COUNT(*) as count FROM bulk_items WHERE auction_id = 2'
            ).fetchone()
            self.assertEqual(result['count'], 0)

    def test_fifo_order_by_auction_id(self):
        """Test that FIFO deduction follows auction_id order"""
        with self.app.app_context():
            db = get_db()
            from tradeTracker.actions import _deduct_bulk_items_fifo
            
            # Add more bulk to auction 4 (created after auction 2 and 3)
            db.execute(
                'INSERT INTO auctions (auction_name, auction_price, auction_profit) '
                'VALUES (?, ?, ?)',
                ('Test Auction 4', 60.0, 0)
            )
            db.execute(
                'INSERT INTO bulk_items (auction_id, item_type, quantity, unit_price, total_price) '
                'VALUES (?, ?, ?, ?, ?)',
                (4, 'bulk', 20, 0.01, 0.20)
            )
            db.commit()
            
            # Deduct 12 bulk
            _deduct_bulk_items_fifo(db, 'bulk', 12)
            db.commit()
            
            # Auction 2 should be fully depleted (had 5)
            result = db.execute(
                'SELECT * FROM bulk_items WHERE auction_id = 2 AND item_type = "bulk"'
            ).fetchone()
            self.assertIsNone(result)
            
            # Auction 3 should have 3 remaining (had 10, deducted 7)
            result = db.execute(
                'SELECT quantity FROM bulk_items WHERE auction_id = 3 AND item_type = "bulk"'
            ).fetchone()
            self.assertEqual(result['quantity'], 3)
            
            # Auction 4 should still have all 20
            result = db.execute(
                'SELECT quantity FROM bulk_items WHERE auction_id = 4 AND item_type = "bulk"'
            ).fetchone()
            self.assertEqual(result['quantity'], 20)


if __name__ == '__main__':
    unittest.main()