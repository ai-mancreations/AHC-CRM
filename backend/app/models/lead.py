from datetime import datetime, timezone
from beanie import Indexed
from app.models.base import AppDocument
from pydantic import Field
from typing import Optional, Dict, Any

from app.models.enums import VisitReasonType, CallOutcome, FollowUpStatus


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Lead(AppDocument):
    branch_id: Indexed(str)
    name: str
    phone: Indexed(str)
    email: Optional[str] = None
    lead_source_id: str  # references SettingsItem(list_type=LEAD_SOURCE)
    lead_status_id: str  # references SettingsItem(list_type=LEAD_STATUS)
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    assigned_to_user_id: Optional[str] = None

    # marketing attribution
    campaign_name: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    ad_campaign_id: Optional[str] = None

    notes: Optional[str] = None
    is_duplicate_of: Optional[str] = None

    converted_customer_id: Optional[str] = None
    converted_at: Optional[datetime] = None
    lost_reason: Optional[str] = None

    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "leads"


class LeadActivity(AppDocument):
    lead_id: Indexed(str)
    branch_id: str
    activity_type: str  # STATUS_CHANGE | NOTE | CALL | WHATSAPP | EMAIL | SYSTEM
    description: str
    performed_by_user_id: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "lead_activities"


class Call(AppDocument):
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    branch_id: Indexed(str)
    direction: str = "OUTBOUND"  # OUTBOUND | INBOUND
    phone: str
    outcome: CallOutcome
    duration_seconds: Optional[int] = None
    notes: Optional[str] = None
    performed_by_user_id: Optional[str] = None
    called_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "calls"


class FollowUp(AppDocument):
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    branch_id: Indexed(str)
    due_date: Indexed(datetime)
    status: FollowUpStatus = FollowUpStatus.PENDING
    notes: Optional[str] = None
    comments: list[dict] = Field(default_factory=list)  # [{text, created_at, user_id}]
    assigned_to_user_id: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "follow_ups"
