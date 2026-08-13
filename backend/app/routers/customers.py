from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User
from app.models.appointment import Customer, Technician
from app.models.service import Service, HairSystemInstallation
from app.models.invoice import Invoice, Payment
from app.models.lead import LeadActivity
from app.core.deps import get_current_user, require_super_admin
from app.services.audit import write_audit

router = APIRouter(prefix="/api/customers", tags=["customers"])
tech_router = APIRouter(prefix="/api/technicians", tags=["technicians"])


class CustomerIn(BaseModel):
    branch_id: str
    name: str
    phone: str
    email: str | None = None
    address: str | None = None
    gst_state_code: str | None = None
    notes: str | None = None


class TechnicianIn(BaseModel):
    branch_id: str
    name: str
    phone: str | None = None
    designation_id: str | None = None
    photo_url: str | None = None


@router.get("")
async def list_customers(branch_id: str | None = None, search: str | None = None,
                          _: User = Depends(get_current_user)):
    query = Customer.find(Customer.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Customer.branch_id == branch_id)
    items = await query.sort("-created_at").to_list()
    if search:
        s = search.lower()
        items = [c for c in items if s in c.name.lower() or s in c.phone]
    return items


@router.post("")
async def create_customer(body: CustomerIn, user: User = Depends(get_current_user)):
    customer = Customer(**body.model_dump())
    await customer.insert()
    await write_audit(user, "CREATE", "customers", str(customer.id), after=customer)
    return customer


@router.get("/{customer_id}/360")
async def customer_360(customer_id: str, _: User = Depends(get_current_user)):
    customer = await Customer.get(customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

    services = await Service.find(Service.customer_id == customer_id).sort("-performed_at").to_list()
    installations = await HairSystemInstallation.find(
        HairSystemInstallation.customer_id == customer_id).sort("-installed_at").to_list()
    invoices = await Invoice.find(Invoice.customer_id == customer_id).sort("-issued_at").to_list()
    invoice_ids = [str(i.id) for i in invoices]
    payments = await Payment.find({"invoice_id": {"$in": invoice_ids}}).to_list() if invoice_ids else []
    activity = []
    if customer.source_lead_id:
        activity = await LeadActivity.find(
            LeadActivity.lead_id == customer.source_lead_id).sort("-created_at").to_list()

    return {
        "customer": customer,
        "services": services,
        "installations": installations,
        "invoices": invoices,
        "payments": payments,
        "timeline": activity,
    }


@router.put("/{customer_id}")
async def update_customer(customer_id: str, body: CustomerIn, user: User = Depends(get_current_user)):
    customer = await Customer.get(customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    before = customer.model_copy()
    for k, v in body.model_dump().items():
        setattr(customer, k, v)
    customer.updated_at = datetime.now(timezone.utc)
    await customer.save()
    await write_audit(user, "UPDATE", "customers", customer_id, before=before, after=customer)
    return customer


@router.post("/{customer_id}/archive")
async def archive_customer(customer_id: str, user: User = Depends(require_super_admin)):
    customer = await Customer.get(customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    customer.is_archived = True
    await customer.save()
    await write_audit(user, "ARCHIVE", "customers", customer_id, after=customer)
    return customer


# ---- Technicians ----

@tech_router.get("")
async def list_technicians(branch_id: str | None = None, _: User = Depends(get_current_user)):
    query = Technician.find(Technician.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Technician.branch_id == branch_id)
    return await query.to_list()


@tech_router.post("")
async def create_technician(body: TechnicianIn, user: User = Depends(get_current_user)):
    tech = Technician(**body.model_dump())
    await tech.insert()
    await write_audit(user, "CREATE", "technicians", str(tech.id), after=tech)
    return tech


@tech_router.get("/{tech_id}/daily-activity")
async def technician_daily_activity(tech_id: str, date_from: datetime | None = None,
                                     date_to: datetime | None = None,
                                     _: User = Depends(get_current_user)):
    query = Service.find(Service.technician_id == tech_id)
    items = await query.to_list()
    if date_from:
        items = [i for i in items if i.performed_at >= date_from]
    if date_to:
        items = [i for i in items if i.performed_at <= date_to]
    return {"technician_id": tech_id, "service_count": len(items), "services": items}
