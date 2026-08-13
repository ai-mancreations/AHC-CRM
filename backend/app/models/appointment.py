from datetime import datetime, timezone
from beanie import Indexed
from app.models.base import AppDocument
from pydantic import Field
from typing import Optional

from app.models.enums import AppointmentStatus, VisitReasonType


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Appointment(AppDocument):
    branch_id: Indexed(str)
    cabin_id: Indexed(str)
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    technician_id: Optional[str] = None
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    start_time: Indexed(datetime)
    end_time: datetime
    status: AppointmentStatus = AppointmentStatus.BOOKED
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = None
    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "appointments"


class WalkIn(AppDocument):
    branch_id: Indexed(str)
    name: str
    phone: str
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    lead_id: Optional[str] = None
    converted_to_appointment_id: Optional[str] = None
    notes: Optional[str] = None
    visited_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "walk_ins"


class Customer(AppDocument):
    branch_id: Indexed(str)
    name: str
    phone: Indexed(str)
    email: Optional[str] = None
    address: Optional[str] = None
    gst_state_code: Optional[str] = None  # customer's state code, for CGST/SGST vs IGST
    source_lead_id: Optional[str] = None
    notes: Optional[str] = None
    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "customers"


class Technician(AppDocument):
    branch_id: Indexed(str)
    name: str
    phone: Optional[str] = None
    designation_id: Optional[str] = None  # SettingsItem(list_type=TECHNICIAN_DESIGNATION)
    photo_url: Optional[str] = None
    is_active: bool = True
    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "technicians"
