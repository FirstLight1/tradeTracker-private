import tradeTracker.services.models as models
from uuid import uuid4

class FakeEPHService:
    def __init__(self):
        pass

    def createSheet(self, parcel_category, reception_method="post", payment_type="h") -> str:
        return f"fake-sheet-{uuid4()}"

    def addParcel(self, order, sheet_id, insurance_value=None, weight=0.5):
        return f"fake-parcel-{uuid4()}"

    def download_label(self, parcel_id, sheet_id, filename):
        pass

    def register_sheet(self, sheet_id):
        return "fake-state"


    def _make_fake_label_pdf(parcel_id, carrier="EPH"):
        buffer = BytesIO()
        width, height = A6

        pdf = canvas.Canvas(buffer, pagesize=A6)
        pdf.setTitle(f"Test {carrier} shipping label")

        pdf.setFillColor(colors.red)
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawCentredString(width / 2, height - 45, "TEST LABEL")

        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawCentredString(
            width / 2,
            height - 65,
            "NOT VALID FOR SHIPPING",
        )

        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(20, height - 105, f"Carrier: {carrier}")

        pdf.setFont("Helvetica", 9)
        pdf.drawString(20, height - 130, "Parcel ID:")
        pdf.drawString(20, height - 145, str(parcel_id))

        pdf.setFont("Helvetica", 10)
        pdf.drawString(20, 45, "Development / staging only")
        pdf.drawString(20, 30, "No shipment was created.")

        pdf.showPage()
        pdf.save()

        return buffer.getvalue()
