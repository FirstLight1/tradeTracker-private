import requests
import json
from zeep import Client
import os

class PacketaService:
    def __init__(self):
        self.client = Client('https://www.zasilkovna.cz/api/soap.wsdl')
        self.api_key = os.environ.get('PACKETA_API_KEY')

    def create_packet(self, order, homeDelivery = False):
        client = self.client
        name,surname = order.reciever.nameAndSurname.split(' ')
        #TODO: required attributes should raise exceptions
        attributes = {
                'number': order.orderId,
                'name': name,
                'surname': surname,
                'addressId': "NEED implementation",
                'email': getattr(order.reciever, 'email', None),
                'value': getattr(order.reciever, 'total', 0),
                'weight': TBD,
                }


        if homeDelivery:

           homeDeliveryAttributes = {
                'phone': order.reciever.phone,
                'addressId': TBD,
                'street': order.reciever.address,
                # TODO: add libposta/pypostal to parse
                'houseNumber': order.reciever.houseNumber,
                'city': order.reciever.city,
                'zip': order.reciever.zipCode,
                #size 
                   }
                
