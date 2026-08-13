from datetime import datetime, timezone
from beanie import Indexed
from app.models.base import AppDocument
from pydantic import Field
from typing import Optional

from app.models.enums import Role


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(AppDocument):
    email: Indexed(str, unique=True)
    password_hash: str
    name: str
    role: Role
    phone: Optional[str] = None
    photo_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "users"


class Branch(AppDocument):
    name: str
    code: Indexed(str, unique=True)
    address: str
    city: str
    state: str
    state_code: str  # GST state code, e.g. "36" for Telangana
    gstin: str
    phone: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "branches"


class Cabin(AppDocument):
    branch_id: Indexed(str)
    name: str
    slot_duration_minutes: int = 90
    is_active: bool = True
    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "cabins"
