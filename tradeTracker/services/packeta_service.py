from zeep import Client
import os
import re
from postal.parser import parse_address
from tradeTracker.CONSTANTS import HEAVY_ARTICLE_CATEGORIES

# Default home-delivery carrier mapping by (country_code, method_token).
# method_token is the lowercase carrier hint from the shipping method name
# (e.g. "hermes" from "Home delivery - Hermes").
DEFAULT_HOME_DELIVERY_CARRIERS = {
    ("de", "hermes"): 6373,          # DE Hermes HD
    ("at", "dpd"): 6830,             # AT DPD HD
    ("fr", "colis privé"): 16080,    # FR Colis Privé Direct HD
    ("fr", "post"): 4309,            # FR Colissimo HD
    ("it", "post"): 29192,           # IT Italian Post HD
    ("be", "post"): 7909,            # BE Belgian Post HD
    ("pl", "post"): 272,             # PL Polish Post 48 HD
    ("lt", "post"): 18808,           # LT Lithuanian Post HD
    ("es", "post"): 4638,            # ES Correos HD
    ("dk", "post"): 4993,            # DK Post Nord HD
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

        method = str(order.shipping.get("shippingMethod") or "").lower()
        method_token = ""
        if "hermes" in method:
            method_token = "hermes"
        elif "colis privé" in method or "colis prive" in method:
            method_token = "colis privé"
        elif "dpd" in method:
            method_token = "dpd"
        elif "post" in method:
            method_token = "post"

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
        category = str(article_info.get("articleCategory") or "")
        if category in HEAVY_ARTICLE_CATEGORIES:
            weight = 1.99
        elif category in HEAVY_ARTICLE_CATEGORIES  and int(article_info.get("articles") or 0) >= 5:
            weight = 2.99

        email = _str_or_fallback(rec.get('email'))
        phone = _str_or_fallback(rec.get('phone'))
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
            length = max(25, 20 + article_count)
            width = 20
            height = max(10, 5 + article_count)
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
