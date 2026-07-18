from zeep import Client
import os
import re
from postal.parser import parse_address
from tradeTracker.CONSTANTS import HEAVY_ARTICLE_CATEGORIES

# Default home-delivery carrier mapping by (country_code, method_token).
# method_token is the lowercase carrier hint from the shipping method name
# (e.g. "hermes" from "Home delivery - Hermes").
DEFAULT_HOME_DELIVERY_CARRIERS = {
    ("pl", "dpd"): 1406,           # PL DPD HD (3000 PLN bracket +0.20; cap ~3000 PLN = ~706 EUR)
    ("cz", "packeta"): 106,        # CZ Packeta Home HD (free to 20 000 CZK; +17% fuel +toll)
    ("sk", "packeta"): 131,        # SK Packeta Home HD (free to 2 000 EUR; +17% fuel +toll)
    ("hu", "express one"): 3828,   # HU Express One HD (free to 100k HUF; 220k +2.60; HARD CAP 220k HUF)
    ("ro", "cargus"): 590,         # RO Cargus HD (1.1% of value >35 RON; cap 3500 RON)
    ("bg", "sameday"): 26066,      # BG Sameday HD (0.7% of value >25 EUR)
    ("hr", "overseas"): 10618,     # HR Overseas HD (free to 700)
    ("si", "express one"): 25004,  # SI Express One HD (free to 700)
    ("at", "dpd"): 6830,           # AT DPD HD (free to 500; 700 +9.50)
    ("gr", "acs"): 17465,          # GR ACS HD (free to 200) — low-value methods
    ("gr", "elta courier"): 27954,    # GR Elta Courier HD (700 +8.30) — high-value method
    ("de", "hermes"): 6373,        # DE Hermes HD (200 +2.00; 700 +6.50)
    ("lt", "venipak"): 25982,      # LT Venipak HD (free to 320) — low-value method
    ("lv", "venipak"): 25981,      # LV Venipak HD (free to 320) — low-value method
    ("lt", "post"): 18808,         # LT Lithuanian Post HD (free to 500; 700 +5.10) — high-value
    ("lv", "post"): 18807,         # LV Lithuanian Post HD (free to 500; 700 +5.10) — high-value
    ("ee", "post"): 18805,         # EE Lithuanian Post HD (free to 500; 700 +5.10)
    ("it", "bartolini"): 9103,     # IT Bartolini HD (200 +0.90; 700 only +3.20)
    ("es", "mrw"): 4653,           # ES MRW HD (free to 100; 200 +2.70; 700 +9.40)
    ("nl", "post"): 4329,          # NL Dutch Post HD (free to 100; 200 +2.60; 700 +9.10)
    ("be", "belgian post"): 7909,  # BE Belgian Post HD (free to 500) — low tier (cheaper than Dutch+fee at 200)
    ("be", "dutch post"): 4832,    # BE Dutch Post HD (700 +9.50) — high tier (cheaper base at 700)
    ("fr", "colissimo"): 4309,     # FR Colissimo HD (free to 150; 300 +2.60; 700 +6.10)
    ("pt", "mrw"): 4655,           # PT MRW HD (free to 100; 200 +2.70; 700 +9.40)
    ("dk", "post nord"): 4993,     # DK Post Nord HD (3700 DKK +0.70; 5200 DKK +9.40 = cap ~697)
    ("lu", "post"): 8125,          # LU Luxembourg Post HD (free to 100; 200 +2.60; 700 +9.00)
    ("fi", "matkahuolto"): 26985,  # FI Matkahuolto HD (free to 320; 700 +9.40)
    ("se", "post nord"): 4827,     # SE Post Nord HD (5000 SEK +0.70; 7500 SEK +8.90 = cap ~676)
}


def _str_or_fallback(val, fallback):
    if val is None:
        return fallback
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return fallback
    except Exception:
        pass
    val = str(val).strip()
    return val if val else fallback


class PacketaService:
    def __init__(self):
        self.client = Client('https://www.zasilkovna.cz/api/soap.wsdl')
        self.api_key = os.environ.get('PACKETA_API_KEY')
        self.FORMAT = "A6 on A6"
        self.OFFSET = 0

    def _home_delivery_carrier_id(self, order):
        rec = order.reciever
        country = str(rec.get("state") or "").strip().lower()
        if country == "d":
            country = "de"

        method = str(order.shipping.get("shippingMethod") or "").lower().strip()
        method = re.sub(r'^home\s*delivery[\s\-:]*', '', method)
        method = method.split('(')[0]
        method = re.sub(r'\s+[a-z]{2}$', '', method)
        method_token = method.strip()

        carrier_id = DEFAULT_HOME_DELIVERY_CARRIERS.get((country, method_token))
        if carrier_id is None:
            carrier_id = int(os.environ.get('PACKETA_HOME_DELIVERY_CARRIER_ID', '0'))
        return carrier_id

    def create_packet(self, order, homeDelivery = False):
        rec = order.reciever
        name, *surname = rec["nameAndSurname"].split(' ')
        surname = ' '.join(surname)

        #TODO: create dict with categories halfway there
        weight = 0.99
        article_info = rec.get("articleInfo") or {}
        categories = [c.strip().lower() for c in str(article_info.get("articleCategory") or "").split(',')]
        if len(categories) > 1 and 'singles' in categories:
            weight = 1.99
        elif len(categories) > 1 and int(article_info.get("articles") or 0) >= 5:
            weight = 2.99

        email = _str_or_fallback(rec.get('email'), "")
        phone = _str_or_fallback(rec.get('phone'), "")
        total = rec.get('total', 0) or 0
        try:
            total = float(total)
        except Exception:
            total = 0.0
        attributes = {
                'number': str(order.idOrder),
                'name': name,
                'surname': surname,
            # TODO: find correct addressId
                'addressId': int(os.environ.get('PACKETA_PICKUP_POINT_ID', '194')),
                'email': email,
                'phone': phone,
                'value': total,
                'weight': weight,
                }


        if homeDelivery:
            raw_address = _str_or_fallback(rec.get("address"), "")
            address = dict(parse_address(raw_address))
            street = _str_or_fallback(address.get('road'), raw_address)
            house_number = _str_or_fallback(address.get('house_number'), "")
            if not house_number:
                m = re.search(r'(\d+[\s\w/]*)$', raw_address)
                if m:
                    house_number = m.group(1).strip()
            article_count = int((rec.get("articleInfo") or {}).get("articles") or 1)
            # Use realistic minimum parcel dimensions; scale slightly with article count.
            length = 600 
            width = 300 
            height = 200 
            homeDeliveryAttributes = {
                    'phone': attributes.get('phone'),
                    'addressId': self._home_delivery_carrier_id(order),
                    'street': street,
                    'houseNumber': house_number,
                    'city': _str_or_fallback(rec.get("city"), ""),
                    'zip': _str_or_fallback(rec.get("zipCode"), ""),
                    'size': {
                        'length': length,
                        'width': width,
                        'height': height,
                        }
                    }
            attributes.update(homeDeliveryAttributes)

        packetIdDetail = self.client.service.createPacket(self.api_key, attributes)
        packetId = packetIdDetail.id
        return packetId


    def packets_labels_pdf(self, packetIds: list):
        PacketIds = self.client.get_type('ns0:PacketIds')
        labes = self.client.service.packetsLabelsPdf(self.api_key, PacketIds(id=packetIds), self.OFFSET, self.FORMAT)
        return labes

    def packet_courier_number(self, packetId):
        res = self.client.service.packetCourierNumberV2(self.api_key, packetId)
        return res.courierNumber


    def packet_courier_labels_pdf(self, packetIds: list):
        PacketIdsWithCourierNumbers = self.client.get_type('ns0:PacketIdsWithCourierNumbers')
        PacketIdWithCourierNumber = self.client.get_type('ns0:PacketIdWithCourierNumber')
        packets = PacketIdsWithCourierNumbers(packetIdWithCourierNumber=[
            PacketIdWithCourierNumber(packetId=p.packetId, courierNumber=p.courierNumber)
            for p in packetIds
        ])
        labels = self.client.service.packetsCourierLabelsPdf(self.api_key, packets, self.OFFSET, self.FORMAT)
        return labels 
