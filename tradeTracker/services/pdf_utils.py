from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph


def wrap_table_text(data, header_font_size=9, body_font_size=10, font_name="DejaVuSans"):
    header_style = ParagraphStyle(
        "TableHeader",
        fontName=font_name,
        fontSize=header_font_size,
        leading=header_font_size + 2,
        alignment=TA_CENTER,
        textColor=colors.white,
        splitLongWords=True,
    )
    body_style = ParagraphStyle(
        "TableBody",
        fontName=font_name,
        fontSize=body_font_size,
        leading=body_font_size + 2,
        alignment=TA_CENTER,
        splitLongWords=True,
    )

    if data and isinstance(data[0], dict):
        columns = list(data[0])
        data = [columns] + [[row.get(column) for column in columns] for row in data]

    return [
        [
            Paragraph(escape(value.replace('_', ' ')), header_style if row_index == 0 else body_style)
            if isinstance(value, str)
            else value
            for value in row
        ]
        for row_index, row in enumerate(data)
    ]
