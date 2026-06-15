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

    
    def getLabel(self, order):
            groups = self.groupByShippingMethod(order["shipping_methods"])
            labels= []
            for category, group in groups.items():
                sheet_id = self.createSheet()
                for order in group: 
                    parcel_id = self.addParcel(order, sheet_id)
                    label = self.download_label(parcel_id, sheet_id)
                    labels.append(label)
            if len(labels) > 0:
                self.register_sheet(sheet_id)
                return labels
            
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

    def groupByShippingMethod(self, shippingMethods)-> dict:
        pass

    def createSheet(self):
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
    def addParcel(self, order, sheet_id):
        parcel = {
            "recipient": {
                "name": order["recipient_name"],
                "street": order["street"],
                "city": order["city"],
                "zip": order["zip"],
                "country": order["country"].lower(),
            }
        }

        if order.get("phone"):
            parcel["recipient"]["phone"] = order["phone"]
        if order.get("email"):
            parcel["recipient"]["email"] = order["email"]
        if order.get("note"):
            parcel["note"] = order["note"]
        if order.get("insurance_value"):
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


