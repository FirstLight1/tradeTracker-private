import tradeTracker.services.models as models
from tradeTracker.utils.fake_pdf_gen import make_fake_label_pdf
from uuid import uuid4


class FakeEPHService:
    def __init__(self):
        pass

    def createSheet(self, parcel_category, reception_method="post", payment_type="h") -> str:
        return f"fake-sheet-{uuid4()}"

    def addParcel(self, order, sheet_id, insurance_value=None, weight=0.5):
        return f"fake-parcel-{uuid4()}"

    def download_label(self, parcel_id, sheet_id, filename):
        return models.LabelResult(filename=filename, bytes=make_fake_label_pdf(parcel_id))

    def register_sheet(self, sheet_id):
        return "fake-state"
