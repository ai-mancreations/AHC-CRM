import csv
import io
import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from app.models.core import User
from app.models.lead import Lead, LeadActivity
from app.models.misc import ImportBatch
from app.models.enums import VisitReasonType, ImportStatus
from app.core.deps import get_current_user

router = APIRouter(prefix="/api/public", tags=["public"])
import_router = APIRouter(prefix="/api/leads/import", tags=["leads-import"])

# very simple in-memory rate limiter: max 5 submissions per IP per 10 minutes
_rate_bucket: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 5
RATE_WINDOW_SECONDS = 600


class PublicLeadIn(BaseModel):
    branch_id: str
    name: str
    phone: str
    email: str | None = None
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    message: str | None = None


@router.post("/lead-form")
async def submit_public_lead(body: PublicLeadIn, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_bucket[client_ip]
    bucket[:] = [t for t in bucket if now - t < RATE_WINDOW_SECONDS]
    if len(bucket) >= RATE_LIMIT:
        raise HTTPException(429, "Too many submissions. Please try again later.")
    bucket.append(now)

    # WEBSITE is a well-known lead_source_id key expected to be seeded; the
    # frontend embed passes the resolved id, but we accept a plain fallback too.
    lead = Lead(
        branch_id=body.branch_id, name=body.name, phone=body.phone, email=body.email,
        lead_source_id="WEBSITE", lead_status_id="NEW", visit_reason=body.visit_reason,
        utm_source=body.utm_source, utm_medium=body.utm_medium, utm_campaign=body.utm_campaign,
        notes=body.message,
    )
    await lead.insert()
    await LeadActivity(
        lead_id=str(lead.id), branch_id=lead.branch_id, activity_type="SYSTEM",
        description="Lead submitted via public website form",
    ).insert()
    return {"ok": True, "lead_id": str(lead.id)}


@router.post("/whatsapp-webhook")
async def whatsapp_inbound_webhook(payload: dict):
    """Stub inbound WhatsApp webhook. Real provider (e.g. Meta Cloud API,
    Twilio, Gupshup) would POST here; wire actual verification/signature
    checks when credentials are configured in Settings > Integrations."""
    phone = payload.get("from") or payload.get("phone")
    message = payload.get("text") or payload.get("message", "")
    branch_id = payload.get("branch_id", "UNASSIGNED")
    if not phone:
        raise HTTPException(400, "Missing sender phone number")

    existing = await Lead.find_one(Lead.phone == phone, Lead.is_archived == False)  # noqa: E712
    if existing:
        await LeadActivity(
            lead_id=str(existing.id), branch_id=existing.branch_id, activity_type="WHATSAPP",
            description=f"Inbound WhatsApp message: {message}",
        ).insert()
        return {"ok": True, "lead_id": str(existing.id), "matched_existing": True}

    lead = Lead(branch_id=branch_id, name=phone, phone=phone, lead_source_id="WHATSAPP",
                lead_status_id="NEW", notes=message)
    await lead.insert()
    await LeadActivity(lead_id=str(lead.id), branch_id=branch_id, activity_type="WHATSAPP",
                        description=f"Inbound WhatsApp message: {message}").insert()
    return {"ok": True, "lead_id": str(lead.id), "matched_existing": False}


@import_router.post("")
async def import_leads_csv(branch_id: str = Form(...), file: UploadFile = File(...),
                            user: User = Depends(get_current_user)):
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)

    batch = ImportBatch(branch_id=branch_id, source_filename=file.filename or "upload.csv",
                         imported_by_user_id=str(user.id), total_rows=len(rows))
    await batch.insert()

    created_ids, dup_count, error_count = [], 0, 0
    for row in rows:
        try:
            phone = (row.get("phone") or row.get("Phone") or "").strip()
            name = (row.get("name") or row.get("Name") or "").strip()
            if not phone or not name:
                error_count += 1
                continue
            existing = await Lead.find_one(Lead.phone == phone, Lead.branch_id == branch_id,
                                            Lead.is_archived == False)  # noqa: E712
            if existing:
                dup_count += 1
                continue
            lead = Lead(
                branch_id=branch_id, name=name, phone=phone,
                email=row.get("email") or row.get("Email"),
                lead_source_id=row.get("lead_source_id", "IMPORT"),
                lead_status_id=row.get("lead_status_id", "NEW"),
                notes=f"Imported from {file.filename}",
            )
            await lead.insert()
            created_ids.append(str(lead.id))
        except Exception:
            error_count += 1

    batch.imported_count = len(created_ids)
    batch.duplicate_count = dup_count
    batch.error_count = error_count
    batch.created_lead_ids = created_ids
    batch.status = ImportStatus.PROCESSED
    await batch.save()
    return batch


@import_router.post("/{batch_id}/rollback")
async def rollback_import(batch_id: str, user: User = Depends(get_current_user)):
    batch = await ImportBatch.get(batch_id)
    if not batch:
        raise HTTPException(404, "Import batch not found")
    if batch.status == ImportStatus.ROLLED_BACK:
        raise HTTPException(400, "Already rolled back")
    for lead_id in batch.created_lead_ids:
        lead = await Lead.get(lead_id)
        if lead:
            lead.is_archived = True
            await lead.save()
    batch.status = ImportStatus.ROLLED_BACK
    await batch.save()
    return batch
