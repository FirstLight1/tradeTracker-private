# Trade Tracker Test Suite

Comprehensive test coverage for Trade Tracker functionality.

## Running the Tests

### Run all tests:
```bash
python -m pytest tests/ -v
```

### Run specific test file:
```bash
# Payment tests
python -m pytest tests/test_payments.py -v

# Bulk/Holo FIFO tests
python -m pytest tests/test_bulk_fifo.py -v
```

Or using unittest:
```bash
python tests/test_payments.py
python tests/test_bulk_fifo.py
```

### Run specific test class:
```bash
python -m pytest tests/test_payments.py::TestPaymentValidation -v
python -m pytest tests/test_bulk_fifo.py::BulkFIFOTestCase -v
```

---

# Bulk/Holo FIFO Inventory Tests

Tests for the First-In-First-Out (FIFO) inventory deduction system.

## Test Coverage

### Inventory Check Tests (3 tests)
Tests for `_check_bulk_inventory()` function:
- ✅ Sufficient inventory validation
- ✅ Insufficient inventory rejection
- ✅ Exact inventory match

### FIFO Deduction Tests (6 tests)
Tests for `_deduct_bulk_items_fifo()` function:
- ✅ Deduction from single auction
- ✅ Complete auction depletion (record deletion)
- ✅ Deduction across multiple auctions
- ✅ All inventory deduction
- ✅ Holo items deduction
- ✅ Correct FIFO order by auction_id

### Integration Tests (3 tests)
End-to-end testing:
- ✅ Invoice endpoint rejects insufficient bulk inventory
- ✅ Invoice endpoint rejects insufficient holo inventory
- ✅ Auction deletion removes bulk_items

## FIFO Deduction Logic

When bulk/holo items are sold, quantities are deducted from the oldest auctions first (by auction_id):

**Example:**
- Auction 2 has 5 bulk items
- Auction 3 has 10 bulk items
- User sells 7 bulk items

**Result:**
- Auction 2: 5 - 5 = 0 (record deleted)
- Auction 3: 10 - 2 = 8 (updated)

## Test Results Expected

All 12 tests should pass:
```
test_check_bulk_inventory_sufficient ... ok
test_check_bulk_inventory_insufficient ... ok
test_check_bulk_inventory_exact ... ok
test_fifo_deduction_single_auction ... ok
test_fifo_deduction_complete_auction ... ok
test_fifo_deduction_multiple_auctions ... ok
test_fifo_deduction_all_inventory ... ok
test_fifo_deduction_holo_items ... ok
test_invoice_insufficient_bulk_inventory ... ok
test_invoice_insufficient_holo_inventory ... ok
test_delete_auction_removes_bulk_items ... ok
test_fifo_order_by_auction_id ... ok

----------------------------------------------------------------------
Ran 12 tests in X.XXXs

OK
```

---

# Payment Functionality Tests

Tests for the payment method validation and security features.

## Test Coverage

### TestPaymentValidation (14 tests)
Tests for the `validate_and_sanitize_payments()` function:
- ✅ Valid single and multiple payments
- ✅ Invalid payment types (whitelist enforcement)
- ✅ XSS injection attempts
- ✅ Negative amounts
- ✅ Non-numeric amounts
- ✅ Amounts too large (>1,000,000)
- ✅ Too many payment methods (>10)
- ✅ Empty and None payment lists
- ✅ Invalid payment object formats
- ✅ Amount rounding to 2 decimal places
- ✅ Zero amounts (allowed)
- ✅ Whitespace handling

### TestPaymentWhitelist (3 tests)
Tests for payment type whitelist configuration:
- ✅ Whitelist exists and is a set
- ✅ Contains all expected payment types
- ✅ Has correct size (7 types)

### TestPaymentEdgeCases (8 tests)
Edge cases and boundary conditions:
- ✅ Very small amounts (0.01)
- ✅ Exact maximum amount (1,000,000)
- ✅ Exact maximum payments (10)
- ✅ Unicode characters in payment types
- ✅ Float precision/rounding
- ✅ Missing 'amount' key
- ✅ Missing 'type' key

## Security Test Coverage

### XSS Protection
- HTML/JavaScript injection in payment types
- Validates against whitelist
- HTML escaping in frontend display

### Data Validation
- Type checking (dict, list, number)
- Range validation (0 to 1,000,000)
- Length validation (max 10 payments)
- Format validation (required keys present)

### Input Sanitization
- Strips/validates whitespace
- Rounds amounts to 2 decimals
- Rejects unauthorized payment types

## Test Results Expected

All 25 tests should pass:
```
test_valid_single_payment ... ok
test_valid_multiple_payments ... ok
test_invalid_payment_type ... ok
test_xss_attempt_in_payment_type ... ok
test_negative_amount ... ok
test_invalid_amount_type ... ok
test_amount_too_large ... ok
test_too_many_payments ... ok
test_empty_payments_list ... ok
test_none_payments ... ok
test_invalid_payment_format ... ok
test_amount_rounding ... ok
test_zero_amount ... ok
test_whitespace_trimming ... ok
test_whitelist_exists ... ok
test_whitelist_contains_expected_types ... ok
test_whitelist_size ... ok
test_very_small_amount ... ok
test_exact_max_amount ... ok
test_exact_max_payments ... ok
test_unicode_in_payment_type ... ok
test_float_precision ... ok
test_missing_amount_key ... ok
test_missing_type_key ... ok

----------------------------------------------------------------------
Ran 25 tests in X.XXXs

OK
```

## Test Data Examples

### Valid Payment
```python
{"type": "Hotovosť", "amount": 100.50}
```

### Invalid Payments (should be rejected)
```python
{"type": "Bitcoin", "amount": 100}  # Not in whitelist
{"type": "Hotovosť", "amount": -50}  # Negative
{"type": "<script>alert('xss')</script>", "amount": 100}  # XSS attempt
{"type": "Hotovosť", "amount": "abc"}  # Non-numeric
```

## Dependencies

These tests require:
- Flask (for test client)
- unittest (standard library)
- The tradeTracker application modules

Make sure you run tests from the project root directory so imports work correctly.
