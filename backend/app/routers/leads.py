from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User
from app.models.lead import Lead, LeadActivity
from app.models.appointment import Customer
from app.models.enums import VisitReasonType, Role
from app.core.deps import get_current_user, require_super_admin
from app.services.audit import write_audit

router = APIRouter(prefix="/api/leads", tags=["leads"])


class LeadIn(BaseModel):
    branch_id: str
    name: str
    phone: str
    email: str | None = None
    lead_source_id: str
    lead_status_id: str
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    assigned_to_user_id: str | None = None
    campaign_name: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    notes: str | None = None


class StatusChangeIn(BaseModel):
    lead_status_id: str


class ConvertIn(BaseModel):
    address: str | None = None
    gst_state_code: str | None = None


@router.get("")
async def list_leads(branch_id: str | None = None, status_id: str | None = None,
                      _: User = Depends(get_current_user)):
    query = Lead.find(Lead.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Lead.branch_id == branch_id)
    if status_id:
        query = query.find(Lead.lead_status_id == status_id)
    return await query.sort("-created_at").to_list()


@router.get("/{lead_id}")
async def get_lead(lead_id: str, _: User = Depends(get_current_user)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    activities = await LeadActivity.find(LeadActivity.lead_id == lead_id).sort("-created_at").to_list()
    return {"lead": lead, "activities": activities}


@router.post("")
async def create_lead(body: LeadIn, user: User = Depends(get_current_user)):
    # duplicate-phone detection (same branch, not archived)
    dup = await Lead.find_one(Lead.phone == body.phone, Lead.branch_id == body.branch_id,
                               Lead.is_archived == False)  # noqa: E712
    lead = Lead(**body.model_dump())
    if dup:
        lead.is_duplicate_of = str(dup.id)
    await lead.insert()
    await LeadActivity(
        lead_id=str(lead.id), branch_id=lead.branch_id, activity_type="SYSTEM",
        description=f"Lead created via manual entry" + (" (possible duplicate detected)" if dup else ""),
        performed_by_user_id=str(user.id),
    ).insert()
    await write_audit(user, "CREATE", "leads", str(lead.id), after=lead)
    return lead


@router.put("/{lead_id}")
async def update_lead(lead_id: str, body: LeadIn, user: User = Depends(get_current_user)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    before = lead.model_copy()
    for k, v in body.model_dump().items():
        setattr(lead, k, v)
    lead.updated_at = datetime.now(timezone.utc)
    await lead.save()
    await write_audit(user, "UPDATE", "leads", str(lead.id), before=before, after=lead)
    return lead


@router.post("/{lead_id}/status")
async def change_status(lead_id: str, body: StatusChangeIn, user: User = Depends(get_current_user)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    old_status = lead.lead_status_id
    lead.lead_status_id = body.lead_status_id
    lead.updated_at = datetime.now(timezone.utc)
    await lead.save()
    await LeadActivity(
        lead_id=lead_id, branch_id=lead.branch_id, activity_type="STATUS_CHANGE",
        description=f"Status changed", performed_by_user_id=str(user.id),
        meta={"from": old_status, "to": body.lead_status_id},
    ).insert()
    return lead


@router.post("/{lead_id}/convert")
async def convert_to_customer(lead_id: str, body: ConvertIn, user: User = Depends(get_current_user)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead.converted_customer_id:
        raise HTTPException(400, "Lead already converted")

    customer = Customer(
        branch_id=lead.branch_id, name=lead.name, phone=lead.phone, email=lead.email,
        address=body.address, gst_state_code=body.gst_state_code, source_lead_id=lead_id,
    )
    await customer.insert()
    lead.converted_customer_id = str(customer.id)
    lead.converted_at = datetime.now(timezone.utc)
    await lead.save()
    await LeadActivity(
        lead_id=lead_id, branch_id=lead.branch_id, activity_type="SYSTEM",
        description="Converted to customer", performed_by_user_id=str(user.id),
    ).insert()
    await write_audit(user, "UPDATE", "leads", lead_id, after=lead)
    return {"lead": lead, "customer": customer}


@router.post("/{lead_id}/archive")
async def archive_lead(lead_id: str, user: User = Depends(require_super_admin)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.is_archived = True
    await lead.save()
    await write_audit(user, "ARCHIVE", "leads", lead_id, after=lead)
    return lead


class NoteIn(BaseModel):
    text: str


@router.post("/{lead_id}/notes")
async def add_note(lead_id: str, body: NoteIn, user: User = Depends(get_current_user)):
    lead = await Lead.get(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    await LeadActivity(
        lead_id=lead_id, branch_id=lead.branch_id, activity_type="NOTE",
        description=body.text, performed_by_user_id=str(user.id),
    ).insert()
    return {"ok": True}
