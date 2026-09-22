import datetime
import unicodedata
import dateutil.parser as dateutil_parser


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

def parse_date_to_iso(value):
    if not value:
        raise ValueError("Empty date value")

    try:
        dt = datetime.datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        pass

    try:
        dt = datetime.datetime.strptime(value, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        pass

    try:
        dt = dateutil_parser.parse(value, dayfirst=True)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError, OverflowError):
        pass

    raise ValueError(
        f"Invalid date format: {value!r}. Expected ISO 8601, YYYY-MM-DD, or dd-mm-yyyy."
    )

def normalize(s: str | None) -> str | None:
    if s is None:
        return None
    # NFD decomposes é → e + combining accent, then encode/decode drops the accent
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").upper()

