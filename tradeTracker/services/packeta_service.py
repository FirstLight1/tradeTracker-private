import requests
import json
from zeep import Client
import os

class PacketaService:
    def __init__(self):
        self.client = Client('https://www.zasilkovna.cz/api/soap.wsdl')
        self.api_key = os.environ.get('PACKETA_API_KEY')

    def create_packet(self, order):
        client = self.client

