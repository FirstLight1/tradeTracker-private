from ast import Tuple

from reportlab.lib import colors
from reportlab.lib import styles
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import datetime
import pandas as pd
from io import BytesIO, TextIOWrapper, StringIO
from typing import Any
import os
import tradeTracker.CONSTANTS as CONSTANTS
from decimal import Decimal
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

    def format_value(self,key, value):
        count_keys = ("card_count", "sealed_count") 
        if key in count_keys:
            return str(value)

        return f"{value:.2f}€"

    def _calculate_header(self, items: list[dict[str, Any]], bulk: list[dict[str, Any]]) -> dict[str, Any]:
        card_count, sealed_count = (
                sum(item.get("item_type") == t for item in items)
                for t in ("card", "sealed")
            )

        total_buy_price = (sum(item.get("buy_price", 0) * item.get('quantity', 1) for item in items)
                        + sum(CONSTANTS.BULK_ITEM_UNIT_PRICES.get(row.get("item_type", 0), "0") * row.get("quantity", 1) for row in bulk))

        total_sell_price = (sum(item.get("sell_price", 0) * item.get('quantity', 1) for item in items)
                        + sum(row['total_price'] or 0 for row in bulk))

        total_profit = Decimal(total_sell_price) - Decimal(total_buy_price)

        total_pos_margin = 0
        total_neg_margin = 0

        for item in items:
            if item.get("item_type") == "sealed" and item['auction_id'] is not None:
                curr_margin = Decimal(item["sell_price"] * item["qty"]) - Decimal(item["buy_price"] * item["qty"])
                if curr_margin > 0:
                    total_pos_margin += curr_margin
                else:
                    total_neg_margin += curr_margin
            else:
                curr_margin = Decimal(item["sell_price"] - item["buy_price"])
                if curr_margin > 0:
                    total_pos_margin += curr_margin
                else:
                    total_neg_margin += curr_margin

        for item in bulk:
            unit_price = CONSTANTS.BULK_ITEM_UNIT_PRICES.get(item["item_type"], 0)
            total_pos_margin += Decimal(item["total_price"] - item["quantity"] * unit_price)

        header_data = {
                'card_count': card_count,
                'sealed_count': sealed_count,
                'total_buy_price': total_buy_price,
                'total_sell_price': total_sell_price,
                'total_profit': total_profit,
                'total_pos_margin': total_pos_margin,
                'total_neg_margin': total_neg_margin,
                'total_margin_profit': total_pos_margin + total_neg_margin
                }
        return header_data

    def _get_auction_data(self, start_date, end_date, id=None):
        raise NotImplementedError

    def _get_purchased_data_month(self, month: int, year: int, id=None) -> list:
        raise NotImplementedError

    def _get_purchased_data_by_id(self, id: int) -> list:
        raise NotImplementedError

    def _get_sold_data_month(self, month: int, year: int, id=None) -> dict:

        curr = self.db.cursor()
        curr.execute(
            """
            SELECT
                c.card_name AS name,
                c.card_num AS item_num,
                c.language AS lang,
                c.card_price AS buy_price,
                si.sell_price AS sell_price,
                ROUND(si.sell_price - c.card_price, 2) AS margin,
                s.sale_date AS sale_date,
                (
                    SELECT TRIM(grader || ' ' || COALESCE(grade_numeric, ''))
                    FROM grading_submission_cards gsc
                    WHERE gsc.card_id = c.id
                    AND gsc.is_current = 1
                ) as grade,
                'card' AS item_type,
                1 AS qty,
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
                se.language AS lang,
                se.price AS buy_price,
                COALESCE(se.sell_price, se.market_value) AS sell_price,
                ROUND(COALESCE(se.sell_price, se.market_value) * se.quantity - se.price * se.quantity, 2) AS margin,
                s.sale_date AS sale_date,
                ' ' as grade,
                'sealed' AS item_type,
                se.quantity AS qty,
                se.auction_id AS auction_id
            FROM sealed se
            JOIN sales s ON se.sale_id = s.id
            WHERE strftime('%Y', s.sale_date) = ?
              AND strftime('%m', s.sale_date) = ?
            """,
            (year, month, year, month),
        )

        itemsData = [dict(row) for row in curr.fetchall()]
        for item in itemsData:
            date = datetime.datetime.strptime(item['sale_date'], "%Y-%m-%d")
            item['sale_date'] = date.strftime("%d.%m.%Y")

        bulkHolo = curr.execute(
            "SELECT item_type, SUM(bs.quantity) as quantity, SUM(bs.total_price) as total_price FROM bulk_sales bs "
            "JOIN sales s ON bs.sale_id = s.id "
            'WHERE strftime("%Y", s.sale_date) = ? AND strftime("%m", s.sale_date) = ?'
            " GROUP BY bs.item_type",
            (year, month),
        )

        bulkData = [dict(item) for item in curr.fetchall()]

        shipping = curr.execute(
            'SELECT shipping_info FROM sales WHERE strftime("%Y", sale_date) = ? AND strftime("%m", sale_date) = ?',
            (year, month),
        )

        shippingData = [dict(item) for item in curr.fetchall()]
        data = {
                "items": itemsData,
                "bulk": bulkData,
                "shipping": shippingData
            }

        return data

    def add_info_header(self, infoHeader: dict[str, Any]) -> Table:
        items = list(infoHeader.items())
        split = (len(items) + 1) // 2

        left = items[:split]
        right = items[split:]

        rows = []

        for i in range(split):
            left_key, left_value = left[i]

            if i < len(right):
                right_key, right_value = right[i]
            else:
                right_key, right_value = "", ""

            rows.append([
                f"{CONSTANTS.LABELS[left_key]}:",
                self.format_value(left_key, left_value),
                f"{CONSTANTS.LABELS[right_key]}:" if right_key else "",
                self.format_value(right_key, right_value) if right_key else "",
            ])

        table = Table(
            rows,
            colWidths=[4 * cm, 2.5 * cm, 4 * cm, 2.5 * cm],
        )
        table.setStyle(TableStyle([
    # No GRID / BOX at all

    ("FONTNAME", (0, 0), (-1, -1), "DejaVuSans"),
    ("FONTSIZE", (0, 0), (-1, -1), 10),

    # Labels
    ("FONTNAME", (0, 0), (0, -1), "DejaVuSans-Bold"),
    ("FONTNAME", (2, 0), (2, -1), "DejaVuSans-Bold"),

    # Values aligned nicely
    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ("ALIGN", (3, 0), (3, -1), "RIGHT"),

    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

    # Vertical spacing
    ("TOPPADDING", (0, 0), (-1, -1), 4),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),

    # Gap between the two halves
    ("LEFTPADDING", (2, 0), (2, -1), 20),

    # Otherwise minimal padding
    ("LEFTPADDING", (0, 0), (1, -1), 0),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
]))
        return table

    def generatePurchaseReport(self, start_date, end_date, month, year, pdf_path):
        pass

    def generateBuyReport(self, start_date, end_date):
        pass

    def generateSoldReport(self, start_date, end_date, month, year, pdf_path):
        doc = SimpleDocTemplate(pdf_path, pagesize=landscape(letter))
        elements = []
        styles = self._styles()

        #TODO: allow periodic report
        elements.append(
            Paragraph(
                "Sales Report - {month}/{year}".format(month=month, year=year), styles["Heading1"]
            )
        )
        elements.append(Spacer(1, 12))

        soldData = self._get_sold_data_month(month, year)
        itemsData = soldData.get("items", [])
        bulkData = soldData.get("bulk", [])
        infoHeader = self._calculate_header(itemsData, bulkData)
        infoHeader['shipping'] = sum(
            float(row.get("shipping_info", 0)) or 0 for row in soldData.get("shipping", [])
        )
        elements.append(self.add_info_header(infoHeader))
        elements.append(Spacer(1, 12))

        if itemsData:
            elements.append(Paragraph("Items", styles["Heading2"]))
            elements.append(Spacer(1, 12))
            table = Table(
                wrap_table_text(itemsData),
                colWidths=[width * mm for width in [35, 24, 14, 25, 25, 25, 25, 17, 20, 15, 17]],
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

        doc.build(elements)
        return pdf_path
