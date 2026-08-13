from datetime import datetime, timezone
from beanie import Indexed
from app.models.base import AppDocument
from pydantic import Field
from typing import Optional, Dict, Any


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# Every simple settings-driven master-data list shares this shape.
# list_type distinguishes the collection's logical purpose, e.g.:
# LEAD_SOURCE, LEAD_STATUS, VISIT_REASON, HAIR_SYSTEM_SIZE, HAIR_SYSTEM_MODEL,
# HAIR_COLOR, HAIR_LENGTH, HAIR_DENSITY, BASE_MATERIAL, INVENTORY_CATEGORY,
# EXPENSE_CATEGORY, TECHNICIAN_DESIGNATION
class SettingsItem(AppDocument):
    list_type: Indexed(str)
    name: str
    sort_order: int = 0
    # free-form extra fields per list_type, e.g. LEAD_STATUS -> {"color": "#C9A227", "is_won": true, "is_lost": false}
    extra: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "settings_items"


class ServiceType(AppDocument):
    name: str
    sac_code: str = "999599"
    description: Optional[str] = None
    base_price: float
    # per-branch overrides keyed by branch code, e.g. {"HYD": 4500}
    branch_price_overrides: Dict[str, float] = Field(default_factory=dict)
    default_gst_rate: float = 18.0
    is_active: bool = True
    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "service_types"

    def price_for_branch(self, branch_code: str) -> float:
        return self.branch_price_overrides.get(branch_code, self.base_price)


class MessageTemplate(AppDocument):
    channel: str  # WHATSAPP | SMS | EMAIL
    name: str
    subject: Optional[str] = None
    body: str  # supports {{placeholders}}
    placeholders: list[str] = Field(default_factory=list)
    trigger_event: Optional[str] = None  # e.g. NEW_LEAD, FOLLOW_UP_DUE, MAINTENANCE_DUE, APPOINTMENT_REMINDER
    is_active: bool = True
    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "message_templates"
