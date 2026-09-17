import datetime
import unicodedata


def format_iso_date(iso_str):
    """Convert an ISO formatted date string to DD.MM.YYYY."""

    if not iso_str:
        return "N/A"

    try:
        date_part = str(iso_str)[:10]

        dt = datetime.datetime.strptime(date_part, "%Y-%m-%d")

        return dt.strftime("%d.%m.%Y")

    except (ValueError, TypeError):
        return str(iso_str)

def normalize(s: str | None) -> str | None:
    if s is None:
        return None
    # NFD decomposes é → e + combining accent, then encode/decode drops the accent
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").upper()

