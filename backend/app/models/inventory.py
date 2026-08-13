from datetime import datetime, timezone
from beanie import Indexed
from app.models.base import AppDocument
from pydantic import Field
from typing import Optional

from app.models.enums import InventoryTxnType, PurchaseOrderStatus


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class InventoryItem(AppDocument):
    branch_id: Indexed(str)
    name: str
    category_id: str  # SettingsItem(list_type=INVENTORY_CATEGORY)
    sku: Optional[str] = None
    unit: str = "pcs"
    stock_qty: float = 0
    reorder_level: float = 5
    unit_cost: float = 0
    expiry_date: Optional[datetime] = None
    supplier_name: Optional[str] = None
    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "inventory_items"

    @property
    def is_low_stock(self) -> bool:
        return self.stock_qty <= self.reorder_level


class InventoryTransaction(AppDocument):
    branch_id: Indexed(str)
    item_id: Indexed(str)
    txn_type: InventoryTxnType
    qty: float  # positive for receipt, negative for deduction
    reference_type: Optional[str] = None  # SERVICE | PURCHASE_ORDER | MANUAL
    reference_id: Optional[str] = None
    notes: Optional[str] = None
    performed_by_user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "inventory_transactions"


class PurchaseOrder(AppDocument):
    branch_id: Indexed(str)
    supplier_name: str
    status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT
    lines: list[dict] = Field(default_factory=list)  # [{item_id, item_name, qty, unit_cost}]
    total_cost: float = 0
    ordered_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "purchase_orders"
