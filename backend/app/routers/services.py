from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User
from app.models.service import Service, HairSystemInstallation
from app.models.inventory import InventoryItem, InventoryTransaction
from app.models.enums import VisitReasonType, InventoryTxnType
from app.core.deps import get_current_user
from app.services.audit import write_audit

router = APIRouter(prefix="/api/services", tags=["services"])
install_router = APIRouter(prefix="/api/installations", tags=["installations"])


class InventoryUse(BaseModel):
    item_id: str
    qty: float


class ServiceIn(BaseModel):
    branch_id: str
    customer_id: str
    technician_id: str | None = None
    service_type_id: str
    appointment_id: str | None = None
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    price_charged: float
    inventory_items_used: list[InventoryUse] = []
    notes: str | None = None


class InstallationIn(BaseModel):
    branch_id: str
    customer_id: str
    technician_id: str | None = None
    service_id: str | None = None
    hair_system_model_id: str
    hair_system_size_id: str
    hair_color_id: str | None = None
    hair_length_id: str | None = None
    hair_density_id: str | None = None
    base_material_id: str | None = None
    installed_at: datetime | None = None
    next_maintenance_due: datetime | None = None
    notes: str | None = None


@router.get("")
async def list_services(branch_id: str | None = None, customer_id: str | None = None,
                         technician_id: str | None = None, _: User = Depends(get_current_user)):
    query = Service.find(Service.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Service.branch_id == branch_id)
    if customer_id:
        query = query.find(Service.customer_id == customer_id)
    if technician_id:
        query = query.find(Service.technician_id == technician_id)
    return await query.sort("-performed_at").to_list()


@router.post("")
async def create_service(body: ServiceIn, user: User = Depends(get_current_user)):
    data = body.model_dump()
    service = Service(**data)
    await service.insert()

    # auto-deduct inventory
    for use in body.inventory_items_used:
        item = await InventoryItem.get(use.item_id)
        if item:
            item.stock_qty = max(0, item.stock_qty - use.qty)
            item.updated_at = datetime.now(timezone.utc)
            await item.save()
            await InventoryTransaction(
                branch_id=item.branch_id, item_id=use.item_id, txn_type=InventoryTxnType.DEDUCTION,
                qty=-abs(use.qty), reference_type="SERVICE", reference_id=str(service.id),
                performed_by_user_id=str(user.id),
            ).insert()

    await write_audit(user, "CREATE", "services", str(service.id), after=service)
    return service


@install_router.get("")
async def list_installations(customer_id: str | None = None, branch_id: str | None = None,
                              _: User = Depends(get_current_user)):
    query = HairSystemInstallation.find()
    if customer_id:
        query = query.find(HairSystemInstallation.customer_id == customer_id)
    if branch_id:
        query = query.find(HairSystemInstallation.branch_id == branch_id)
    return await query.sort("-installed_at").to_list()


@install_router.post("")
async def create_installation(body: InstallationIn, user: User = Depends(get_current_user)):
    data = body.model_dump()
    if not data.get("installed_at"):
        data["installed_at"] = datetime.now(timezone.utc)
    installation = HairSystemInstallation(**data)
    await installation.insert()
    await write_audit(user, "CREATE", "hair_system_installations", str(installation.id), after=installation)
    return installation


@install_router.post("/{installation_id}/replace")
async def replace_installation(installation_id: str, body: InstallationIn, user: User = Depends(get_current_user)):
    old = await HairSystemInstallation.get(installation_id)
    if not old:
        raise HTTPException(404, "Installation not found")
    old.is_active = False
    await old.save()

    data = body.model_dump()
    if not data.get("installed_at"):
        data["installed_at"] = datetime.now(timezone.utc)
    data["replacement_of_installation_id"] = installation_id
    new_install = HairSystemInstallation(**data)
    await new_install.insert()
    await write_audit(user, "CREATE", "hair_system_installations", str(new_install.id), after=new_install)
    return new_install
