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
            "x-api-auth": f"apikey {self.user_id}:{self.api_key}",
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


    def createSheet(self, parcel_category, reception_method = 'post', payment_type = "h" ) -> str:
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

    #TODO: add service categories
    def addParcel(self, order, sheet_id, insurance_value = None):
        country = order.get("state", "") or ""
        if country == "D":
            country = "DE"

        parcel = {
            "recipient": {
                "name": order.get("nameAndSurname", ""),
                "street": order.get("address", ""),
                "city": order.get("city", ""),
                "zip": order.get("zip", ""),
                "country": country.lower(),
                "phone": order.get("phone", ""),
                "email": order.get("email", ""),
            }, 
        }

        if insurance_value:
            parcel["insurance"] = {
                "value": int(insurance_value),
                "currency": "eur",
            }

        r = requests.put(
            f"{self.baseurl}/sheets/{sheet_id}/parcels",
            json={"parcel": parcel},
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()["parcel"]["id"]

    def download_label(self, parcel_id, sheet_id, filename):
        r = requests.post(
            f"{self.baseurl}/sheets/{sheet_id}/parcels/{parcel_id}/labels",
            json={"format": "pdf"},
            headers=self._headers(),
        )
        r.raise_for_status()
        label_url = r.json()["labels"]["url"]

        pdf = requests.get(label_url)
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


