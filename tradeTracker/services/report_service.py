from reportlab.lib import colors
from reportlab.lib import styles
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pandas as pd
from io import BytesIO, TextIOWrapper, StringIO
from typing import Any
import os

from tradeTracker.services.pdf_utils import wrap_table_text


class ReportService:
    def __init__(self, db):
        self.db = db
        self.font_dir = os.path.join(os.path.dirname(__file__).replace("services", "fonts"))
        pdfmetrics.registerFont(TTFont("DejaVuSans", os.path.join(self.font_dir, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(
            TTFont("DejaVuSans-Bold", os.path.join(self.font_dir, "DejaVuSans-Bold.ttf"))
        )
        pdfmetrics.registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold")

    def _styles(self):
        styles = getSampleStyleSheet()
        styles["Heading1"].fontName = "DejaVuSans"
        styles["Heading2"].fontName = "DejaVuSans"
        return styles

    def _table_style(self):
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ]
        )

    def _get_auction_data(self, start_date, end_date, id=None):
        raise NotImplementedError

    def _get_purchased_data(self, start_date, end_date, id=None):
        if id:
            where_clause = "auction_id = ?"
        else:
            where_clause = 'WHERE strftime("%Y", substr(date_created, 1, 19)) = ? AND strftime("%m", substr(date_created, 1, 19)) = ? '

        pass

    def _get_sold_data(self, start_date, end_date, month, year, id=None):

        curr = self.db.cursor()
        items = curr.execute(
            """
            SELECT
                c.card_name AS name,
                c.card_num AS item_num,
                c.card_price AS purchase_price,
                c.language AS language,
                si.sell_price AS sell_price,
                s.sale_date AS sale_date,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM grading_submission_cards gsc
                    WHERE gsc.card_id = c.id
                      AND gsc.is_current = 1
                ) THEN 1 ELSE 0 END AS is_graded,
                'card' AS item_type,
                1 AS quantity,
                NULL AS auction_id
            FROM cards c
            JOIN sale_items si ON c.id = si.card_id
            JOIN sales s ON si.sale_id = s.id
            WHERE strftime('%Y', s.sale_date) = ?
              AND strftime('%m', s.sale_date) = ?

            UNION ALL

            SELECT
                se.name AS name,
                NULL AS item_num,
                se.price AS purchase_price,
                NULL AS language,
                COALESCE(se.sell_price, se.market_value) AS sell_price,
                s.sale_date AS sale_date,
                0 AS is_graded,
                'sealed' AS item_type,
                se.quantity AS quantity,
                se.auction_id AS auction_id
            FROM sealed se
            JOIN sales s ON se.sale_id = s.id
            WHERE strftime('%Y', s.sale_date) = ?
              AND strftime('%m', s.sale_date) = ?
            """,
            (year, month, year, month),
        )

        itemDesc = [desc[0] for desc in curr.description]
        itemsRows = [row[:6] + ("True" if row[6] else "",) + row[7:] for row in curr.fetchall()]
        itemsData = [itemDesc] + itemsRows

        bulkHolo = curr.execute(
            "SELECT item_type, SUM(bs.quantity) as quantity, SUM(bs.total_price) as total_price FROM bulk_sales bs "
            "JOIN sales s ON bs.sale_id = s.id "
            'WHERE strftime("%Y", s.sale_date) = ? AND strftime("%m", s.sale_date) = ?'
            " GROUP BY bs.item_type",
            (year, month),
        )

        bulkDesc = [desc[0] for desc in curr.description]
        bulkItems = [dict(item) for item in curr.fetchall()]
        bulkData = [bulkDesc] + bulkItems

        shipping = curr.execute(
            'SELECT shipping_info FROM sales WHERE strftime("%Y", sale_date) = ? AND strftime("%m", sale_date) = ?',
            (year, month),
        )

        shippingDesc = [desc[0] for desc in curr.description]
        shippingInfo = [dict(item) for item in curr.fetchall()]
        shippingData = [shippingDesc] + shippingInfo

        return itemsData, bulkData, shippingData

    def generateSoldReport(self, start_date, end_date):
        pass

    def generateBuyReport(self, start_date, end_date):
        pass

    def generatePurchaseReport(self, start_date, end_date, month, year, pdf_path):
        doc = SimpleDocTemplate(pdf_path, pagesize=landscape(letter))
        elements = []
        styles = self._styles()

        # TODO: switch to periodic report
        # TODO: remove unnecessary data
        # TODO: format headers
        elements.append(
            Paragraph(
                "Sales Report - {month}/{year}".format(month=month, year=year), styles["Heading1"]
            )
        )
        elements.append(Spacer(1, 12))

        itemsData, bulkData, shippingData = self._get_sold_data(None, None, month, year)

        if itemsData:
            elements.append(Paragraph("Items", styles["Heading2"]))
            elements.append(Spacer(1, 12))
            table = Table(
                wrap_table_text(itemsData),
                colWidths=[width * mm for width in [35, 24, 25, 14, 25, 25, 17, 20, 15, 25]],
                repeatRows=1,
            )
            table.setStyle(self._table_style())
            elements.append(table)
            elements.append(Spacer(1, 12))

        if bulkData:
            elements.append(Paragraph("Bulk", styles["Heading2"]))
            elements.append(Spacer(1, 12))
            table = Table(wrap_table_text(bulkData), repeatRows=1)
            table.setStyle(self._table_style())
            elements.append(table)
            elements.append(Spacer(1, 12))

        if shippingData:
            elements.append(Paragraph("shipping", styles["Heading2"]))
            elements.append(Spacer(1, 12))
            table = Table(wrap_table_text(shippingData), repeatRows=1)
            table.setStyle(self._table_style())
            elements.append(table)
            elements.append(Spacer(1, 12))

        doc.build(elements)
        return pdf_path
