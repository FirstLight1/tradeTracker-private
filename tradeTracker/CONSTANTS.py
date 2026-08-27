from decimal import Decimal


CENT = Decimal("0.01")


ALLOWED_PAYMENT_TYPES = {
    "Hotovosť",
    "Karta",
    "Barter",
    "Bankový prevod",
    "Online platba",
    "Dobierka",
    "Online platobný systém",
}

BULK_ITEM_UNIT_PRICES = {"bulk": 0.01, "holo": 0.03, "ex": 0.15}

COlLUMN_MAP = {
    "name": "card_name",
    "setCode": "set_code",
    "cn": "set_number",
    "condition": "condition",
    "price": "market_value",
    "listedAt": "date_created",
    "quantity": "quantity",
}

CONDITION_DICT = {
    "MT": "MINT",
    "NM": "NEAR MINT",
    "EX": "EXCELLENT",
    "GD": "GOOD",
    "LP": "LIGHT PLAYED",
    "PL": "PLAYED",
    "PO": "POOR",
}

ALLOWED_LANGUAGES = {
    "en",
    "jp",
    "de",
    "fr",
    "it",
    "es",
    "kr",
    "cn",
    "pt",
}

LANGUAGE_FULL_TO_ABB = {
    "english": "en",
    "japanese": "jp",
    "german": "de",
    "french": "fr",
    "italian": "it",
    "spanish": "es",
    "korean": "kr",
    "chinese": "cn",
    "simplified chinese": "cn",
    "s-chinese": "cn",
    "portuguese": "pt",
}

LANGUAGE_ABB_TO_FULL = {
    "en": "english",
    "jp": "japanese",
    "de": "german",
    "fr": "french",
    "it": "italian",
    "es": "spanish",
    "kr": "korean",
    "cn": "chinese",
    "cn": "simplified chinese",
    "cn": "s-chinese",
    "pt": "portuguese",
}


PARCEL_CATEGORIES = {
    "registered letter": "r",
    "letter": "olz",
    "insured letter": "pl",
    "parcel": "b",
}

HEAVY_ARTICLE_CATEGORIES = {
    "Booster",
    "Display",
    "Box Set",
    "Elite Trainer Boxes",
}

EUROPE_COUNTRY_CODES = {
    "albania": "AL",
    "andorra": "AD",
    "austria": "AT",
    "belarus": "BY",
    "belgium": "BE",
    "bosnia and herzegovina": "BA",
    "bulgaria": "BG",
    "croatia": "HR",
    "cyprus": "CY",
    "czech republic": "CZ",
    "cesko": "CZ",
    "denmark": "DK",
    "estonia": "EE",
    "finland": "FI",
    "france": "FR",
    "fermany": "DE",
    "greece": "GR",
    "hungary": "HU",
    "iceland": "IS",
    "ireland": "IE",
    "italy": "IT",
    "latvia": "LV",
    "liechtenstein": "LI",
    "lithuania": "LT",
    "luxembourg": "LU",
    "malta": "MT",
    "moldova": "MD",
    "monaco": "MC",
    "montenegro": "ME",
    "netherlands": "NL",
    "north macedonia": "MK",
    "norway": "NO",
    "poland": "PL",
    "portugal": "PT",
    "romania": "RO",
    "russia": "RU",
    "san marino": "SM",
    "serbia": "RS",
    "slovakia": "SK",
    "slovensko": "SK",
    "slovenia": "SI",
    "spain": "ES",
    "sweden": "SE",
    "switzerland": "CH",
    "turkey": "TR",
    "ukraine": "UA",
    "united kingdom": "GB",
    "vatican city": "VA",
}
