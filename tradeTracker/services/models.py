from dataclasses import dataclass
import enum
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
    RAW = "raw"
    PREPARING = "preparing"
    SENT_FOR_GRADING = "sent_for_grading"
    RECEIVED_BY_GRADER = "received_by_grader"
    GRADED = "graded"
    RETURNED = "returned"
    CANCELLED = "cancelled"   

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
                    grader=(
                        str(item["grader"])
                        if item.get("grader") is not None
                        else None
                    ),
                    grading_fee=float(item["grading_fee"]),
                    submitted_value=float(item["submitted_value"]),
                    prep_fee=float(item.get("prep_fee", 0.0)),
                    upcharge=float(item.get("upcharge", 0.0)),
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
        grader = str(item["grader"]),
        service_level = (
            str(item['service_level'])
            if item.get('service_level') is not None
            else None
            ),
        status = GradeStatus(item["status"]),
        submitted_at = item["submitted_at"],
        returned_at = (
            str(item["returned_at"])
            if item.get("returned_at") is not None
            else None
            ),
        notes = (
            item["notes"]
            if item.get("notes") is not None
            else None
            ),
        cards = [],
        outbound_shipping_cost = float(item["outbound_shipping_cost"]),
        return_shipping_cost = float(item.get("return_shipping_cost", 0.0)),
        insurance_cost = float(item.get("insurance_cost", 0.0)),
        customs_duty_cost = float(item.get("customs_duty_cost", 0.0)),
        other_shared_cost = float(item.get("other_shared_cost", 0.0)),
        )


     
@dataclass
class GradingCompleteItems:
    card_id: int
    grade_numeric: float | None
    grade_label: str | None
    qualifier: str | None 
    cert_number: str | None
    post_grade_market_value: float | None

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "GradingCompleteItems":
        return cls(
            card_id=int(item["card_id"]),
            grade_numeric=float(item["grade_numeric"]),
            grade_label=str(item["grade_label"]),
            qualifier=(
                str(item["qualifier"])
                if item.get("qualifier") is not None
                else None
            ),
            cert_number=(
                str(item["cert_number"])
                if item.get("cert_number") is not None
                else None
            ),
            post_grade_market_value=(
                float(item["post_grade_market_value"])
                if item.get("post_grade_market_value") is not None
                else None
            ),
        )




