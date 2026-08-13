from datetime import datetime, timezone
from beanie import Indexed
from app.models.base import AppDocument
from pydantic import Field
from typing import Optional

from app.models.enums import VisitReasonType


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Service(AppDocument):
    branch_id: Indexed(str)
    customer_id: Indexed(str)
    technician_id: Optional[str] = None
    service_type_id: str
    appointment_id: Optional[str] = None
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    price_charged: float
    inventory_items_used: list[dict] = Field(default_factory=list)  # [{item_id, qty}]
    notes: Optional[str] = None
    invoice_id: Optional[str] = None
    performed_at: datetime = Field(default_factory=now_utc)
    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "services"


class HairSystemInstallation(AppDocument):
    branch_id: Indexed(str)
    customer_id: Indexed(str)
    technician_id: Optional[str] = None
    service_id: Optional[str] = None
    hair_system_model_id: str
    hair_system_size_id: str
    hair_color_id: Optional[str] = None
    hair_length_id: Optional[str] = None
    hair_density_id: Optional[str] = None
    base_material_id: Optional[str] = None
    installed_at: datetime = Field(default_factory=now_utc)
    next_maintenance_due: Optional[datetime] = None
    replacement_of_installation_id: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "hair_system_installations"
