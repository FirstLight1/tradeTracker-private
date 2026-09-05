from dataclasses import dataclass
import enum
from tradeTracker.services.grading_validation import (
    grade_number,
    money,
    normalize_date,
    normalize_text,
)
from typing import Any
import datetime


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
    idOrder: str | None = None


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


@dataclass
class LabelResult:
    filename: str
    bytes: bytes


@dataclass
class EPHSheetInfo:
    sheetId: str
    state: str | None
    parcelId: str
    filename: str | None
    label: bytes | None


@dataclass
class PacketaHomeDeliveryResult:
    packetId: str
    courierNumber: str


class GradeStatus(enum.StrEnum):
    PREPARING = "preparing"
    SENT_FOR_GRADING = "sent_for_grading"
    RECEIVED_BY_GRADER = "received_by_grader"
    GRADED = "graded"
    RETURNED = "returned"
    CANCELLED = "cancelled"

    @property
    def is_active(self) -> bool:
        return self in {
            GradeStatus.PREPARING,
            GradeStatus.SENT_FOR_GRADING,
            GradeStatus.RECEIVED_BY_GRADER,
        }

    @property
    def is_terminal(self) -> bool:
        return self in {GradeStatus.GRADED, GradeStatus.RETURNED, GradeStatus.CANCELLED}


@dataclass
class GradingSubmissionCard:
    card_id: int
    grader: str | None
    grading_fee: float
    submitted_value: float
    prep_fee: float = 0.0
    upcharge: float = 0.0

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "GradingSubmissionCard":
        return cls(
            card_id=int(item["card_id"]),
            grader=normalize_text(item.get("grader"), "grader"),
            grading_fee=float(money(item.get("grading_fee", 0), "grading_fee")),
            submitted_value=float(money(item.get("submitted_value", 0), "submitted_value")),
            prep_fee=float(money(item.get("prep_fee", 0), "prep_fee")),
            upcharge=float(money(item.get("upcharge", 0), "upcharge")),
        )


@dataclass
class GradingSubmission:
    grader: str
    service_level: str | None
    status: GradeStatus
    submitted_at: str
    returned_at: str | None
    notes: str | None
    cards: list[GradingSubmissionCard]
    outbound_shipping_cost: float = 0.0
    return_shipping_cost: float = 0.0
    insurance_cost: float = 0.0
    customs_duty_cost: float = 0.0
    other_shared_cost: float = 0.0

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "GradingSubmission":
        return cls(
            grader=normalize_text(item.get("grader"), "grader", required=True),
            service_level=(normalize_text(item.get("service_level"), "service_level")),
            status=GradeStatus(item["status"]),
            submitted_at=normalize_date(item.get("submitted_at"), "submitted_at", required=True),
            returned_at=normalize_date(item.get("returned_at"), "returned_at"),
            notes=normalize_text(item.get("notes"), "notes"),
            cards=[],
            outbound_shipping_cost=float(
                money(item.get("outbound_shipping_cost", 0), "outbound_shipping_cost")
            ),
            return_shipping_cost=float(
                money(item.get("return_shipping_cost", 0), "return_shipping_cost")
            ),
            insurance_cost=float(money(item.get("insurance_cost", 0), "insurance_cost")),
            customs_duty_cost=float(money(item.get("customs_duty_cost", 0), "customs_duty_cost")),
            other_shared_cost=float(money(item.get("other_shared_cost", 0), "other_shared_cost")),
        )


@dataclass
class GradingCompleteItems:
    card_id: int
    grade_numeric: float | None
    grade_label: str | None
    qualifier: str | None
    cert_number: str | None
    post_grade_market_value: float | None
    grader: str | None = None

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "GradingCompleteItems":
        return cls(
            card_id=int(item["card_id"]),
            grade_numeric=(lambda value: float(value) if value is not None else None)(
                grade_number(item.get("grade_numeric"))
            ),
            grader=normalize_text(item.get("grader"), "grader"),
            grade_label=normalize_text(item.get("grade_label"), "grade_label"),
            qualifier=normalize_text(item.get("qualifier"), "qualifier"),
            cert_number=normalize_text(item.get("cert_number"), "cert_number"),
            post_grade_market_value=(lambda value: float(value) if value is not None else None)(
                money(item.get("post_grade_market_value"), "post_grade_market_value", nullable=True)
            ),
        )
