import requests
import os
import tradeTracker.services.models as models
import json
import io
import time
from datetime import datetime

class EPHService:
    def __init__(self):
        self.api_key = os.environ.get("EPH_API_KEY")
        self.user_id = os.environ.get("EPH_USER_ID")
        self.baseurl = "https://mojezasielky.posta.sk/integration/rest/v1"

    def _headers(self):
        return {
                "X-API-Key": f"apikey: {self.user_id}: {self.api_key}",
            "Content-Type": "application/json",
        }

    def _getSender(self):
        return {
            "name": os.environ["SENDER_NAME"],
            "street": os.environ["SENDER_STREET"],
            "city": os.environ["SENDER_CITY"],
            "zip": os.environ["SENDER_ZIP"],
            "country": "sk",
            "phone": os.environ["SENDER_PHONE"],
            "email": os.environ["SENDER_EMAIL"],
        }


#TODO: add service categories
    def createSheet(self, parcel_category, reception_method, payment_type = "h" ) -> str:
        payload = {
            "sheet": {
                "parcel_category": parcel_category,
                "payment_type": payment_type,
                "reception_method": reception_method,
                "sender": self._getSender(),
            }

        }

        r = requests.put(f"{self.baseurl}/sheets", json=payload, headers=self._headers())
        r.raise_for_status()
        return r.json()["sheet"]["id"]

    #TODO: check with EPH if this is the correct way to do it
    #TODO: add service categories
    def addParcel(self, order, sheet_id, insurance_value = None):
        if order["shippingAddressCountry"] == "D":
            order["shippingAddressCountry"] = "DE"

        parcel = {
            "recipient": {
                "name": order["nameAndSurname"],
                "street": order["address"],
                "city": order["city"],
                "zip": order["zipCode"],
                "country": order["state"].lower(),
            }
        }

        if insurance_value:
            parcel["insurance"] = {
                "value": int(order["insurance_value"]),
                "currency": "eur",
            }

        r = requests.put(
            f"{self.baseurl}/sheets/{sheet_id}/parcels",
            json={"parcel": parcel},
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()["parcel"]

    #TODO: add filename
    def download_label(self, parcel_id, sheet_id, filename):
        r = requests.get(
            f"{self.baseurl}/sheets/{sheet_id}/parcels/{parcel_id}/label",
            headers=self._headers(),
        )
        r.raise_for_status()
        label_url = r.json()["label"]["url"]

        pdf = requests.get(label_url, headers=self._headers())
        pdf.raise_for_status()
        
        return models.LabelResult(filename=filename, bytes=pdf.content)

    def register_sheet(self, sheet_id):
        r = requests.post(
            f"{self.baseurl}/sheets/{sheet_id}/register",
            json = {},
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()["sheet"]["state"]


