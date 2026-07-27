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

class GradeStatus(enum.strEnum):
    RAW = "raw"
    PREPARING = "preparing"
    SENT_FOR_GRADING = "sent_for_grading"
    RECEIVED_BY_GRADER = "received_by_grader"
    GRADED = "graded"
    RETURNED = "returned"
    CANCELLED = "cancelled"   

@dataclass
class GradingSubmission:
    grader: str 
    service_level :str
    status: GradeStatus
    outbound_shipping_cost: float = 0.0
    return_shipping_cost: float = 0.0
    insurance_cost: float = 0.0
    customs_duty_cost: float = 0.0
    other_shared_cost: float = 0.0
    submitted_at: datetime.datetime
    returned_at: datetime.datetime | None
    notes: str | None
    cards: list[GradingSubmissionCard]


@dataclass
class GradingSubmissionCard:
    card_id: int
    grader: str
    grading_fee: float
    submitted_value: float
    prep_fee: float = 0.0
    upcharge: float | None
     
@dataclass
class GradingCompleteItems:
    card_id: int
    grade_numeric: float
    grade_label: str
    qualifier: str | None 
    cert_number: str | None
    post_grade_market_value: float | None




