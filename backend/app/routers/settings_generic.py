from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any

from app.models.core import User
from app.models.settings_entity import SettingsItem, ServiceType, MessageTemplate
from app.models.config import CompanyConfig, Integration
from app.core.deps import get_current_user, require_super_admin
from app.core.security import encrypt_secret
from app.services.audit import write_audit

router = APIRouter(prefix="/api/settings", tags=["settings"])

LIST_TYPES = [
    "LEAD_SOURCE", "LEAD_STATUS", "VISIT_REASON", "HAIR_SYSTEM_SIZE", "HAIR_SYSTEM_MODEL",
    "HAIR_COLOR", "HAIR_LENGTH", "HAIR_DENSITY", "BASE_MATERIAL", "INVENTORY_CATEGORY",
    "EXPENSE_CATEGORY", "TECHNICIAN_DESIGNATION",
]


class SettingsItemIn(BaseModel):
    list_type: str
    name: str
    sort_order: int = 0
    extra: dict[str, Any] = {}


class ReorderIn(BaseModel):
    ordered_ids: list[str]


@router.get("/lists/{list_type}")
async def list_items(list_type: str, include_archived: bool = False, _: User = Depends(get_current_user)):
    query = SettingsItem.find(SettingsItem.list_type == list_type)
    items = await query.sort("+sort_order").to_list()
    if not include_archived:
        items = [i for i in items if not i.is_archived]
    return items


@router.post("/lists")
async def create_item(body: SettingsItemIn, user: User = Depends(require_super_admin)):
    if body.list_type not in LIST_TYPES:
        raise HTTPException(400, f"Unknown list_type. Must be one of {LIST_TYPES}")
    item = SettingsItem(**body.model_dump())
    await item.insert()
    await write_audit(user, "CREATE", "settings_items", str(item.id), after=item)
    return item


@router.put("/lists/{item_id}")
async def update_item(item_id: str, body: SettingsItemIn, user: User = Depends(require_super_admin)):
    item = await SettingsItem.get(item_id)
    if not item:
        raise HTTPException(404, "Not found")
    before = item.model_copy()
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    item.updated_at = datetime.now(timezone.utc)
    await item.save()
    await write_audit(user, "UPDATE", "settings_items", str(item.id), before=before, after=item)
    return item


@router.post("/lists/{item_id}/archive")
async def archive_item(item_id: str, user: User = Depends(require_super_admin)):
    item = await SettingsItem.get(item_id)
    if not item:
        raise HTTPException(404, "Not found")
    before = item.model_copy()
    item.is_archived = True
    await item.save()
    await write_audit(user, "ARCHIVE", "settings_items", str(item.id), before=before, after=item)
    return item


@router.post("/lists/reorder")
async def reorder_items(body: ReorderIn, user: User = Depends(require_super_admin)):
    for idx, item_id in enumerate(body.ordered_ids):
        item = await SettingsItem.get(item_id)
        if item:
            item.sort_order = idx
            await item.save()
    return {"ok": True}


# ---- Service Types ----

class ServiceTypeIn(BaseModel):
    name: str
    sac_code: str = "999599"
    description: str | None = None
    base_price: float
    branch_price_overrides: dict[str, float] = {}
    default_gst_rate: float = 18.0


@router.get("/service-types")
async def list_service_types(_: User = Depends(get_current_user)):
    return await ServiceType.find(ServiceType.is_archived == False).to_list()  # noqa: E712


@router.post("/service-types")
async def create_service_type(body: ServiceTypeIn, user: User = Depends(require_super_admin)):
    st = ServiceType(**body.model_dump())
    await st.insert()
    await write_audit(user, "CREATE", "service_types", str(st.id), after=st)
    return st


@router.put("/service-types/{st_id}")
async def update_service_type(st_id: str, body: ServiceTypeIn, user: User = Depends(require_super_admin)):
    st = await ServiceType.get(st_id)
    if not st:
        raise HTTPException(404, "Not found")
    before = st.model_copy()
    for k, v in body.model_dump().items():
        setattr(st, k, v)
    await st.save()
    await write_audit(user, "UPDATE", "service_types", str(st.id), before=before, after=st)
    return st


# ---- Message Templates ----

class MessageTemplateIn(BaseModel):
    channel: str
    name: str
    subject: str | None = None
    body: str
    placeholders: list[str] = []
    trigger_event: str | None = None


@router.get("/message-templates")
async def list_templates(_: User = Depends(get_current_user)):
    return await MessageTemplate.find(MessageTemplate.is_archived == False).to_list()  # noqa: E712


@router.post("/message-templates")
async def create_template(body: MessageTemplateIn, user: User = Depends(require_super_admin)):
    tpl = MessageTemplate(**body.model_dump())
    await tpl.insert()
    await write_audit(user, "CREATE", "message_templates", str(tpl.id), after=tpl)
    return tpl


# ---- Company / GST config ----

class CompanyConfigIn(BaseModel):
    company_name: str
    fy_start_month: int = 4
    default_cgst_rate: float = 9.0
    default_sgst_rate: float = 9.0
    default_igst_rate: float = 18.0


@router.get("/company-config")
async def get_company_config(_: User = Depends(get_current_user)):
    cfg = await CompanyConfig.find_one()
    if not cfg:
        cfg = CompanyConfig()
        await cfg.insert()
    return cfg


@router.put("/company-config")
async def update_company_config(body: CompanyConfigIn, user: User = Depends(require_super_admin)):
    cfg = await CompanyConfig.find_one()
    if not cfg:
        cfg = CompanyConfig(**body.model_dump())
        await cfg.insert()
    else:
        for k, v in body.model_dump().items():
            setattr(cfg, k, v)
        cfg.updated_at = datetime.now(timezone.utc)
        await cfg.save()
    await write_audit(user, "UPDATE", "company_config", str(cfg.id), after=cfg)
    return cfg


# ---- Integrations (encrypted credentials) ----

class IntegrationIn(BaseModel):
    provider: str
    is_enabled: bool = False
    credentials: dict[str, Any] = {}  # plaintext in, encrypted at rest


@router.get("/integrations")
async def list_integrations(user: User = Depends(require_super_admin)):
    items = await Integration.find_all().to_list()
    # never return decrypted secrets to the client
    return [{"id": str(i.id), "provider": i.provider, "is_enabled": i.is_enabled,
             "has_credentials": bool(i.encrypted_credentials)} for i in items]


@router.put("/integrations/{provider}")
async def upsert_integration(provider: str, body: IntegrationIn, user: User = Depends(require_super_admin)):
    import json
    integration = await Integration.find_one(Integration.provider == provider)
    encrypted = encrypt_secret(json.dumps(body.credentials)) if body.credentials else None
    if not integration:
        integration = Integration(provider=provider, is_enabled=body.is_enabled, encrypted_credentials=encrypted)
        await integration.insert()
    else:
        integration.is_enabled = body.is_enabled
        if encrypted:
            integration.encrypted_credentials = encrypted
        integration.updated_at = datetime.now(timezone.utc)
        await integration.save()
    await write_audit(user, "UPDATE", "integrations", str(integration.id))
    return {"ok": True}
