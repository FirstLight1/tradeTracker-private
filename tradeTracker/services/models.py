from dataclasses import dataclass
from typing import Any

@dataclass
class Payment:
    type: str
    amount: float

@dataclass
class SaleInput:
    reciever: dict[str, Any]
    cards: list[dict[str, Any]]
    sealed: list[dict[str, Any]]
    bulk: dict[str, Any] | None
    holo: dict[str, Any] | None
    ex: dict[str, Any] | None
    shipping: dict[str, Any] | None
    payments: list[Payment]

@dataclass
class ReceiptResult:
    kind: str
    number: str
    file_path: str | None = None
    raw: dict[str, Any] | None = None

@dataclass
class SaleResult:
    sale_id: int
    receipt: ReceiptResult
