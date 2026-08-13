from datetime import datetime, timezone
from beanie import Indexed
from app.models.base import AppDocument
from pydantic import Field
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class CompanyConfig(AppDocument):
    """Singleton document (one row) holding GST/FY-wide settings."""
    company_name: str = "American Hair Club"
    fy_start_month: int = 4  # April
    default_cgst_rate: float = 9.0
    default_sgst_rate: float = 9.0
    default_igst_rate: float = 18.0
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "company_config"


class Integration(AppDocument):
    provider: Indexed(str, unique=True)  # GOOGLE_ADS | META_ADS | WHATSAPP | SMS | EMAIL
    is_enabled: bool = False
    # encrypted (Fernet) JSON-serialized credential blob
    encrypted_credentials: Optional[str] = None
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "integrations"


class Counter(AppDocument):
    """Atomic counters, e.g. invoice numbering per branch per financial year."""
    key: Indexed(str, unique=True)  # e.g. "INV-HYD-FY2526"
    value: int = 0

    class Settings:
        name = "counters"
