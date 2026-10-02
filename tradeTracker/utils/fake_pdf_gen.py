from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A6
from reportlab.pdfgen import canvas


def make_fake_label_pdf(parcel_id, carrier="EPH"):
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
