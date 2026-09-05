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
import json
import tradeTracker.CONSTANTS as CONSTANTS
from tradeTracker.utils.formating import format_iso_date
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
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ]
        )

    #TODO: move to utils
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

    def _get_buy_data_period(self, start_date, end_date, id=None):
        raise NotImplementedError

    def _get_buy_data_month(self, month: int, year: int) -> pd.DataFrame:
        rows = self.db.execute('SELECT auction_name,auction_price, date_created, payment_method FROM auctions '
                        'WHERE strftime("%Y", substr(date_created, 1, 19)) = ? AND strftime("%m", substr(date_created, 1, 19)) = ? '
                        ,(year,month))
        bought = {"Meno": [], "Cena": [], "Datum": [], "Payment type": [], "Amount": []}
    
        for row in rows:
            bought["Meno"].append(row["auction_name"])
            try:
                bought["Cena"].append(Decimal(row["auction_price"]))
            except:
                bought["Cena"].append("Error")
            bought["Datum"].append(format_iso_date(row["date_created"]))
            if row["payment_method"] != None:
                payments = json.loads(row["payment_method"])
                bought["Payment type"].append(", ".join(payment["type"] for payment in payments))
                bought["Amount"].append(", ".join(str(payment["amount"]) for payment in payments))
            else:
                bought["Payment type"].append("")
                bought["Amount"].append("")
    
        df = pd.DataFrame(bought)
        return df

    def get_auction_data(self, id: int) -> dict[str, Any]:
        auctionInfo = self.db.execute("SELECT id, auction_name, date_created FROM auctions "
                                  "WHERE id = ?", (id,)).fetchone()
        auctionName = (
            auctionInfo[1] if auctionInfo[1] is not None else f"auction {int(auctionInfo[0]) - 1}"
        )
        dateCreated = format_iso_date(auctionInfo[2])
        data = { "auctionName": auctionName, "dateCreated": dateCreated }
        return data

    def _get_purchased_data_month(self, month: int, year: int, id=None) -> list:
        raise NotImplementedError

    def _get_purchased_data_by_id(self, id: int) -> dict[str,Any]:
        curr = self.db.cursor()
        curr.execute(
            """
            SELECT
    card_name AS name,
    card_num AS item_num,
    condition,
    language,
    card_price AS 'buy price',
    market_value AS 'market value',
    CASE WHEN sold_date IS NOT NULL THEN 'true' ELSE '' END AS sold,
    NULL AS opened,
    'card' AS item_type
FROM cards
WHERE auction_id = ?

UNION ALL

SELECT
    name,
    NULL AS item_num,
    NULL AS condition,
    NULL AS language,
    price AS 'buy price',
    market_value AS 'market value',
    CASE WHEN sale_id IS NOT NULL THEN 'true' ELSE '' END AS sold,
    CASE WHEN opened = 1 THEN 'true' ELSE '' END AS opened,
    'sealed' AS item_type
FROM sealed
WHERE auction_id = ?
        """
        ,(id, id))

        itemsData = [dict(row) for row in curr.fetchall()]

        bulk = curr.execute("SELECT item_type, SUM(quantity) as quantity FROM bulk_items "
                                 "WHERE auction_id = ? GROUP BY item_type", (id,)).fetchall()
        bulkData = [dict(row) for row in bulk]

        purchasedData = { 'items': itemsData, 'bulk': bulkData }

        return purchasedData

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

    def generatePurchaseReport(self, id: int):
        auctionData = self.get_auction_data(id)
        purchasedData = self._get_purchased_data_by_id(id)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        elements = []
        styles = self._styles()

        elements.append(
            Paragraph(f"Sales Report - {auctionData['auctionName']} - Added: {auctionData['dateCreated']}", styles["Heading1"])
        )
        elements.append(Spacer(1, 12))

        itemsData = purchasedData.get("items", [])
        bulkData = purchasedData.get("bulk", [])

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

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return auctionData["auctionName"], pdf

    def generateBuyReport(self, start_date, end_date, month, year, xls_path):
        df = self._get_buy_data_month(month, year)
        with pd.ExcelWriter(xls_path) as writer:
            df.to_excel(writer, sheet_name="nakupy", index=False)
    
            worksheet = writer.sheets["nakupy"]
            worksheet.column_dimensions["A"].width = 24
            worksheet.column_dimensions["B"].width = 12
            worksheet.column_dimensions["C"].width = 11
            worksheet.column_dimensions["D"].width = 30
            worksheet.column_dimensions["E"].width = 20
    
            for row in range(2, len(df) + 2):
                cell = worksheet[f"B{row}"]
                cell.number_format = '#,##.00 "€"'
    
            for row in range(2, len(df) + 2):
                cell = worksheet[f"D{row}"]
                cell.number_format = '#,##.00 "€"'
    
        return xls_path

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
