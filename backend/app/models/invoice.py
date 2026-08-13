from datetime import datetime, timezone
from beanie import Indexed
from app.models.base import AppDocument
from pydantic import BaseModel, Field
from typing import Optional

from app.models.enums import GstType, InvoiceStatus, PaymentMethod


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class InvoiceLine(BaseModel):
    description: str
    hsn_sac_code: str
    service_type_id: Optional[str] = None
    inventory_item_id: Optional[str] = None
    qty: float = 1
    unit_price: float
    taxable_value: float
    gst_rate: float = 18.0
    cgst_amount: float = 0
    sgst_amount: float = 0
    igst_amount: float = 0
    line_total: float


class Invoice(AppDocument):
    branch_id: Indexed(str)
    customer_id: Indexed(str)
    invoice_number: Indexed(str, unique=True)  # e.g. AHC/HYD/2526/0001
    financial_year: str  # e.g. "2025-26"
    gst_type: GstType
    lines: list[InvoiceLine] = Field(default_factory=list)
    subtotal: float = 0
    total_cgst: float = 0
    total_sgst: float = 0
    total_igst: float = 0
    grand_total: float = 0
    amount_paid: float = 0
    status: InvoiceStatus = InvoiceStatus.DRAFT
    due_date: Optional[datetime] = None
    pdf_url: Optional[str] = None
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = None
    is_archived: bool = False
    issued_at: datetime = Field(default_factory=now_utc)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "invoices"

    @property
    def balance_due(self) -> float:
        return round(self.grand_total - self.amount_paid, 2)


class Payment(AppDocument):
    invoice_id: Indexed(str)
    branch_id: str
    amount: float
    method: PaymentMethod
    reference_no: Optional[str] = None
    paid_at: datetime = Field(default_factory=now_utc)
    recorded_by_user_id: Optional[str] = None
    notes: Optional[str] = None

    class Settings:
        name = "payments"
