ALLOWED_PAYMENT_TYPES = {
    'Hotovosť',
    'Karta',
    'Barter',
    'Bankový prevod',
    'Online platba',
    'Dobierka',
    'Online platobný systém'
}

BULK_ITEM_UNIT_PRICES = {
    'bulk': 0.01,
    'holo': 0.03,
    'ex': 0.15
}

COlLUMN_MAP ={
    'name': 'card_name',
    'setCode': 'set_code',
    'cn': 'set_number',
    'condition': 'condition',
    'price': 'market_value',
    'listedAt': 'date_created',
    'quantity': 'quantity',
}

CONDITION_DICT = {
    'MT' : "MINT",
    'NM' : "NEAR MINT",
    'EX' : "EXCELLENT",
    'GD' : "GOOD",
    'LP' : "LIGHT PLAYED",
    'PL' : "PLAYED",
    'PO' : "POOR"
}

