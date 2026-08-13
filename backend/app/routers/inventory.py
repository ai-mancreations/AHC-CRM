from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User
from app.models.inventory import InventoryItem, InventoryTransaction, PurchaseOrder
from app.models.enums import InventoryTxnType, PurchaseOrderStatus
from app.core.deps import get_current_user, require_super_admin
from app.services.audit import write_audit

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


class InventoryItemIn(BaseModel):
    branch_id: str
    name: str
    category_id: str
    sku: str | None = None
    unit: str = "pcs"
    stock_qty: float = 0
    reorder_level: float = 5
    unit_cost: float = 0
    expiry_date: datetime | None = None
    supplier_name: str | None = None


class TxnIn(BaseModel):
    branch_id: str
    item_id: str
    txn_type: InventoryTxnType
    qty: float
    notes: str | None = None


class POLine(BaseModel):
    item_id: str
    item_name: str
    qty: float
    unit_cost: float


class POIn(BaseModel):
    branch_id: str
    supplier_name: str
    lines: list[POLine]
    notes: str | None = None


@router.get("/items")
async def list_items(branch_id: str | None = None, low_stock_only: bool = False,
                      expiring_within_days: int | None = None, _: User = Depends(get_current_user)):
    query = InventoryItem.find(InventoryItem.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(InventoryItem.branch_id == branch_id)
    items = await query.to_list()
    if low_stock_only:
        items = [i for i in items if i.is_low_stock]
    if expiring_within_days is not None:
        cutoff = datetime.now(timezone.utc) + timedelta(days=expiring_within_days)
        items = [i for i in items if i.expiry_date and i.expiry_date <= cutoff]
    return items


@router.post("/items")
async def create_item(body: InventoryItemIn, user: User = Depends(get_current_user)):
    item = InventoryItem(**body.model_dump())
    await item.insert()
    await write_audit(user, "CREATE", "inventory_items", str(item.id), after=item)
    return item


@router.put("/items/{item_id}")
async def update_item(item_id: str, body: InventoryItemIn, user: User = Depends(get_current_user)):
    item = await InventoryItem.get(item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    before = item.model_copy()
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    item.updated_at = datetime.now(timezone.utc)
    await item.save()
    await write_audit(user, "UPDATE", "inventory_items", item_id, before=before, after=item)
    return item


@router.get("/transactions")
async def list_transactions(item_id: str | None = None, branch_id: str | None = None,
                             _: User = Depends(get_current_user)):
    query = InventoryTransaction.find()
    if item_id:
        query = query.find(InventoryTransaction.item_id == item_id)
    if branch_id:
        query = query.find(InventoryTransaction.branch_id == branch_id)
    return await query.sort("-created_at").to_list()


@router.post("/transactions")
async def create_transaction(body: TxnIn, user: User = Depends(get_current_user)):
    item = await InventoryItem.get(body.item_id)
    if not item:
        raise HTTPException(404, "Inventory item not found")
    item.stock_qty = max(0, item.stock_qty + body.qty)
    item.updated_at = datetime.now(timezone.utc)
    await item.save()
    txn = InventoryTransaction(**body.model_dump(), performed_by_user_id=str(user.id))
    await txn.insert()
    return txn


@router.get("/purchase-orders")
async def list_pos(branch_id: str | None = None, status: PurchaseOrderStatus | None = None,
                    _: User = Depends(get_current_user)):
    query = PurchaseOrder.find()
    if branch_id:
        query = query.find(PurchaseOrder.branch_id == branch_id)
    if status:
        query = query.find(PurchaseOrder.status == status)
    return await query.sort("-created_at").to_list()


@router.post("/purchase-orders")
async def create_po(body: POIn, user: User = Depends(get_current_user)):
    lines = [l.model_dump() for l in body.lines]
    total = sum(l["qty"] * l["unit_cost"] for l in lines)
    po = PurchaseOrder(branch_id=body.branch_id, supplier_name=body.supplier_name, lines=lines,
                        total_cost=total, notes=body.notes, created_by_user_id=str(user.id))
    await po.insert()
    return po


@router.post("/purchase-orders/{po_id}/status")
async def set_po_status(po_id: str, status: PurchaseOrderStatus, user: User = Depends(get_current_user)):
    po = await PurchaseOrder.get(po_id)
    if not po:
        raise HTTPException(404, "Purchase order not found")
    po.status = status
    now = datetime.now(timezone.utc)
    if status == PurchaseOrderStatus.ORDERED:
        po.ordered_at = now
    if status == PurchaseOrderStatus.RECEIVED:
        po.received_at = now
        # receiving stock updates inventory
        for line in po.lines:
            item = await InventoryItem.get(line["item_id"])
            if item:
                item.stock_qty += line["qty"]
                await item.save()
                await InventoryTransaction(
                    branch_id=po.branch_id, item_id=line["item_id"], txn_type=InventoryTxnType.RECEIPT,
                    qty=line["qty"], reference_type="PURCHASE_ORDER", reference_id=po_id,
                    performed_by_user_id=str(user.id),
                ).insert()
    await po.save()
    return po
