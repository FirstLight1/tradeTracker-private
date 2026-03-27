"""
Test suite for payment method functionality.
Tests validation, sanitization, and API endpoints.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import json
from tradeTracker import create_app
from tradeTracker.db import get_db, init_db
from tradeTracker.actions import validate_and_sanitize_payments, ALLOWED_PAYMENT_TYPES


class TestPaymentValidation(unittest.TestCase):
    """Test payment validation and sanitization functions."""
    
    def test_valid_single_payment(self):
        """Test validation with a single valid payment."""
        payments = [{"type": "Hotovosť", "amount": 100.50}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        self.assertEqual(len(sanitized), 1)
        self.assertEqual(sanitized[0]["type"], "Hotovosť")
        self.assertEqual(sanitized[0]["amount"], 100.50)
    
    def test_valid_multiple_payments(self):
        """Test validation with multiple valid payments."""
        payments = [
            {"type": "Hotovosť", "amount": 50.00},
            {"type": "Karta", "amount": 75.25},
            {"type": "Barter", "amount": 25.50}
        ]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        self.assertEqual(len(sanitized), 3)
    
    def test_invalid_payment_type(self):
        """Test validation rejects invalid payment types."""
        payments = [{"type": "Bitcoin", "amount": 100}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertIn("Invalid payment type", error)
    
    def test_xss_attempt_in_payment_type(self):
        """Test validation rejects XSS attempts in payment type."""
        payments = [{"type": "<script>alert('xss')</script>", "amount": 100}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
    
    def test_negative_amount(self):
        """Test validation rejects negative amounts."""
        payments = [{"type": "Hotovosť", "amount": -50}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertFalse(is_valid)
        self.assertIn("cannot be negative", error)
    
    def test_invalid_amount_type(self):
        """Test validation rejects non-numeric amounts."""
        payments = [{"type": "Hotovosť", "amount": "not a number"}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertFalse(is_valid)
        self.assertIn("Invalid payment amount", error)
    
    def test_amount_too_large(self):
        """Test validation rejects excessively large amounts."""
        payments = [{"type": "Hotovosť", "amount": 2000000}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertFalse(is_valid)
        self.assertIn("too large", error)
    
    def test_too_many_payments(self):
        """Test validation rejects more than 10 payment methods."""
        payments = [{"type": "Hotovosť", "amount": 10} for _ in range(11)]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertFalse(is_valid)
        self.assertIn("Too many", error)
    
    def test_empty_payments_list(self):
        """Test validation rejects empty payment list."""
        payments = []
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertFalse(is_valid)
        self.assertIn("At least one payment", error)
    
    def test_none_payments(self):
        """Test validation rejects None."""
        is_valid, sanitized, error = validate_and_sanitize_payments(None)
        
        self.assertFalse(is_valid)
        self.assertIn("Invalid payments format", error)
    
    def test_invalid_payment_format(self):
        """Test validation rejects invalid payment object format."""
        payments = ["not a dict"]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertFalse(is_valid)
        self.assertIn("Invalid payment object", error)
    
    def test_amount_rounding(self):
        """Test that amounts are rounded to 2 decimal places."""
        payments = [{"type": "Hotovosť", "amount": 100.12345}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertTrue(is_valid)
        self.assertEqual(sanitized[0]["amount"], 100.12)
    
    def test_zero_amount(self):
        """Test that zero amounts are allowed."""
        payments = [{"type": "Hotovosť", "amount": 0}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertTrue(is_valid)
        self.assertEqual(sanitized[0]["amount"], 0.00)


class TestPaymentWhitelist(unittest.TestCase):
    """Test that the payment type whitelist is properly defined."""
    
    def test_whitelist_exists(self):
        """Test that ALLOWED_PAYMENT_TYPES is defined."""
        self.assertIsNotNone(ALLOWED_PAYMENT_TYPES)
        self.assertIsInstance(ALLOWED_PAYMENT_TYPES, set)
    
    def test_whitelist_contains_expected_types(self):
        """Test that whitelist contains expected payment types."""
        expected_types = [
            'Hotovosť',
            'Karta',
            'Barter',
            'Bankový prevod',
            'Online platba',
            'Dobierka',
            'Online platobný systém'
        ]
        
        for payment_type in expected_types:
            self.assertIn(payment_type, ALLOWED_PAYMENT_TYPES)
    
    def test_whitelist_size(self):
        """Test that whitelist has expected number of payment types."""
        self.assertEqual(len(ALLOWED_PAYMENT_TYPES), 7)


class TestPaymentEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def test_very_small_amount(self):
        """Test with very small (but positive) amount."""
        payments = [{"type": "Hotovosť", "amount": 0.01}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertTrue(is_valid)
        self.assertEqual(sanitized[0]["amount"], 0.01)
    
    def test_exact_max_amount(self):
        """Test with amount exactly at maximum."""
        payments = [{"type": "Hotovosť", "amount": 1000000}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertTrue(is_valid)
        self.assertEqual(sanitized[0]["amount"], 1000000.00)
    
    def test_exact_max_payments(self):
        """Test with exactly 10 payment methods (max allowed)."""
        payments = [{"type": "Hotovosť", "amount": 10} for _ in range(10)]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertTrue(is_valid)
        self.assertEqual(len(sanitized), 10)
    
    def test_unicode_in_payment_type(self):
        """Test that unicode characters in payment types work correctly."""
        payments = [{"type": "Bankový prevod", "amount": 100}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertTrue(is_valid)
        self.assertEqual(sanitized[0]["type"], "Bankový prevod")
    
    def test_float_precision(self):
        """Test float precision is handled correctly."""
        payments = [{"type": "Hotovosť", "amount": 99.99999}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertTrue(is_valid)
        # Should be rounded to 2 decimal places
        self.assertEqual(sanitized[0]["amount"], 100.00)
    
    def test_missing_amount_key(self):
        """Test payment object missing 'amount' key."""
        payments = [{"type": "Hotovosť"}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertFalse(is_valid)
    
    def test_missing_type_key(self):
        """Test payment object missing 'type' key."""
        payments = [{"amount": 100}]
        is_valid, sanitized, error = validate_and_sanitize_payments(payments)
        
        self.assertFalse(is_valid)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
