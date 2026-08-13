from datetime import datetime, timezone
from beanie import Indexed
from app.models.base import AppDocument
from pydantic import Field
from typing import Optional, Dict, Any

from app.models.enums import ImportStatus, NotificationType


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Expense(AppDocument):
    branch_id: Indexed(str)
    category_id: str  # SettingsItem(list_type=EXPENSE_CATEGORY)
    description: str
    amount: float
    receipt_url: Optional[str] = None
    is_recurring: bool = False
    incurred_at: Indexed(datetime)
    recorded_by_user_id: Optional[str] = None
    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "expenses"


class AdCampaign(AppDocument):
    branch_id: Optional[str] = None  # None = company-wide campaign
    platform: str  # GOOGLE_ADS | META_ADS
    campaign_name: str
    external_campaign_id: Optional[str] = None
    spend: float = 0
    impressions: int = 0
    clicks: int = 0
    leads_generated: int = 0
    conversions: int = 0
    period_start: datetime
    period_end: datetime
    last_synced_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "ad_campaigns"

    @property
    def cpl(self) -> float:
        return round(self.spend / self.leads_generated, 2) if self.leads_generated else 0

    @property
    def cac(self) -> float:
        return round(self.spend / self.conversions, 2) if self.conversions else 0


class Notification(AppDocument):
    user_id: Optional[str] = None  # None = broadcast to all users of role/branch
    branch_id: Optional[str] = None
    type: NotificationType
    title: str
    message: str
    link: Optional[str] = None
    is_read: bool = False
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "notifications"


class AuditLog(AppDocument):
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    action: str  # CREATE | UPDATE | ARCHIVE | DELETE | LOGIN
    collection_name: str
    document_id: str
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "audit_logs"


class ImportBatch(AppDocument):
    branch_id: Indexed(str)
    source_filename: str
    imported_by_user_id: Optional[str] = None
    total_rows: int = 0
    imported_count: int = 0
    duplicate_count: int = 0
    error_count: int = 0
    created_lead_ids: list[str] = Field(default_factory=list)
    status: ImportStatus = ImportStatus.PENDING
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "import_batches"
