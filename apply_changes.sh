#!/bin/bash
# Run this from inside: /c/dev/american-hair-club_pythonversion/american-hair-club
set -e
echo "Applying changes..."

mkdir -p "$(dirname "backend/app/models/lead.py")"
cat > "backend/app/models/lead.py" << 'PYEOF_0'
from datetime import datetime, timezone
from beanie import Document, Indexed
from pydantic import Field
from typing import Optional, Dict, Any

from app.models.enums import VisitReasonType, CallOutcome, FollowUpStatus


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Lead(Document):
    branch_id: Indexed(str)
    name: str
    phone: Indexed(str)
    email: Optional[str] = None
    lead_source_id: str  # references SettingsItem(list_type=LEAD_SOURCE)
    lead_status_id: str  # references SettingsItem(list_type=LEAD_STATUS)
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    assigned_to_user_id: Optional[str] = None

    # marketing attribution
    campaign_name: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    ad_campaign_id: Optional[str] = None

    notes: Optional[str] = None
    is_duplicate_of: Optional[str] = None

    converted_customer_id: Optional[str] = None
    converted_at: Optional[datetime] = None
    lost_reason: Optional[str] = None

    is_archived: bool = False
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "leads"


class LeadActivity(Document):
    lead_id: Indexed(str)
    branch_id: str
    activity_type: str  # STATUS_CHANGE | NOTE | CALL | WHATSAPP | EMAIL | SYSTEM
    description: str
    performed_by_user_id: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "lead_activities"


class Call(Document):
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    branch_id: Indexed(str)
    direction: str = "OUTBOUND"  # OUTBOUND | INBOUND
    phone: str
    outcome: CallOutcome
    duration_seconds: Optional[int] = None
    notes: Optional[str] = None
    performed_by_user_id: Optional[str] = None
    called_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "calls"


class FollowUp(Document):
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    branch_id: Indexed(str)
    due_date: Indexed(datetime)
    status: FollowUpStatus = FollowUpStatus.PENDING
    notes: Optional[str] = None
    comments: list[dict] = Field(default_factory=list)  # [{text, created_at, user_id}]
    assigned_to_user_id: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=now_utc)

    class Settings:
        name = "follow_ups"
PYEOF_0
echo "  wrote backend/app/models/lead.py"

mkdir -p "$(dirname "backend/app/routers/calls_followups.py")"
cat > "backend/app/routers/calls_followups.py" << 'PYEOF_1'
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User
from app.models.lead import Call, FollowUp, LeadActivity
from app.models.enums import CallOutcome, FollowUpStatus
from app.core.deps import get_current_user

router = APIRouter(prefix="/api", tags=["calls-followups"])


class CallIn(BaseModel):
    lead_id: str | None = None
    customer_id: str | None = None
    branch_id: str
    direction: str = "OUTBOUND"
    phone: str
    outcome: CallOutcome
    duration_seconds: int | None = None
    notes: str | None = None


class FollowUpIn(BaseModel):
    lead_id: str | None = None
    customer_id: str | None = None
    branch_id: str
    due_date: datetime
    notes: str | None = None
    assigned_to_user_id: str | None = None


class CommentIn(BaseModel):
    text: str


class CompleteIn(BaseModel):
    comment: str | None = None
    reschedule_due_date: datetime | None = None
    reschedule_notes: str | None = None


@router.get("/calls")
async def list_calls(branch_id: str | None = None, lead_id: str | None = None,
                      _: User = Depends(get_current_user)):
    query = Call.find()
    if branch_id:
        query = query.find(Call.branch_id == branch_id)
    if lead_id:
        query = query.find(Call.lead_id == lead_id)
    return await query.sort("-called_at").to_list()


@router.post("/calls")
async def log_call(body: CallIn, user: User = Depends(get_current_user)):
    call = Call(**body.model_dump(), performed_by_user_id=str(user.id))
    await call.insert()
    if body.lead_id:
        await LeadActivity(
            lead_id=body.lead_id, branch_id=body.branch_id, activity_type="CALL",
            description=f"Call logged: {body.outcome.value}", performed_by_user_id=str(user.id),
        ).insert()
    return call


@router.get("/follow-ups")
async def list_follow_ups(branch_id: str | None = None, bucket: str | None = None,
                           _: User = Depends(get_current_user)):
    """bucket: today | overdue | upcoming"""
    query = FollowUp.find(FollowUp.status == FollowUpStatus.PENDING)
    if branch_id:
        query = query.find(FollowUp.branch_id == branch_id)
    items = await query.sort("+due_date").to_list()

    if bucket:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)
        if bucket == "overdue":
            items = [i for i in items if i.due_date < today_start]
        elif bucket == "today":
            items = [i for i in items if today_start <= i.due_date <= today_end]
        elif bucket == "upcoming":
            items = [i for i in items if i.due_date > today_end]
    return items


@router.post("/follow-ups")
async def create_follow_up(body: FollowUpIn, _: User = Depends(get_current_user)):
    fu = FollowUp(**body.model_dump())
    await fu.insert()
    return fu


@router.post("/follow-ups/{fu_id}/comments")
async def add_comment(fu_id: str, body: CommentIn, user: User = Depends(get_current_user)):
    fu = await FollowUp.get(fu_id)
    if not fu:
        raise HTTPException(404, "Follow-up not found")
    fu.comments.append({
        "text": body.text,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_id": str(user.id),
        "user_name": user.name,
    })
    await fu.save()
    return fu


@router.post("/follow-ups/{fu_id}/complete")
async def complete_follow_up(fu_id: str, body: CompleteIn | None = None, user: User = Depends(get_current_user)):
    fu = await FollowUp.get(fu_id)
    if not fu:
        raise HTTPException(404, "Follow-up not found")

    body = body or CompleteIn()
    if body.comment:
        fu.comments.append({
            "text": body.comment,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "user_id": str(user.id),
            "user_name": user.name,
        })

    fu.status = FollowUpStatus.DONE
    fu.completed_at = datetime.now(timezone.utc)
    await fu.save()

    new_follow_up = None
    if body.reschedule_due_date:
        new_follow_up = FollowUp(
            lead_id=fu.lead_id, customer_id=fu.customer_id, branch_id=fu.branch_id,
            due_date=body.reschedule_due_date, notes=body.reschedule_notes or fu.notes,
            assigned_to_user_id=fu.assigned_to_user_id,
        )
        await new_follow_up.insert()

    return {"completed": fu, "next_follow_up": new_follow_up}
PYEOF_1
echo "  wrote backend/app/routers/calls_followups.py"

mkdir -p "$(dirname "backend/seed.py")"
cat > "backend/seed.py" << 'PYEOF_2'
"""
Loads a complete, realistic demo dataset for American Hair Club CRM.

Usage:
    python seed.py            # wipes and reloads all demo data
    python seed.py --keep     # loads only if collections are empty

Run this after the app's .env is configured to point at your Mongo instance.
"""
import asyncio
import argparse
import random
from datetime import datetime, timedelta, timezone

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import ALL_DOCUMENT_MODELS
from app.models.core import User, Branch, Cabin
from app.models.enums import (
    Role, VisitReasonType, AppointmentStatus, CallOutcome, FollowUpStatus,
    GstType, InvoiceStatus, PaymentMethod, PurchaseOrderStatus, InventoryTxnType,
)
from app.models.settings_entity import SettingsItem, ServiceType, MessageTemplate
from app.models.config import CompanyConfig, Integration, Counter
from app.models.lead import Lead, LeadActivity, Call, FollowUp
from app.models.appointment import Appointment, WalkIn, Customer, Technician
from app.models.service import Service, HairSystemInstallation
from app.models.inventory import InventoryItem, InventoryTransaction, PurchaseOrder
from app.models.invoice import Invoice, InvoiceLine, Payment
from app.models.misc import Expense, AdCampaign, Notification, AuditLog
from app.services.gst import determine_gst_type, compute_line_tax, financial_year_label, financial_year_short_code

random.seed(42)
NOW = datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return NOW - timedelta(days=n)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

BRANCHES = [
    dict(name="American Hair Club - Hyderabad", code="HYD", city="Hyderabad", state="Telangana",
         state_code="36", gstin="36AAACH1234A1Z5", address="Road No. 12, Banjara Hills, Hyderabad", cabins=4),
    dict(name="American Hair Club - Pune", code="PUN", city="Pune", state="Maharashtra",
         state_code="27", gstin="27AAACH1234A1Z2", address="FC Road, Shivajinagar, Pune", cabins=2),
    dict(name="American Hair Club - Vizag", code="VIZ", city="Visakhapatnam", state="Andhra Pradesh",
         state_code="37", gstin="37AAACH1234A1Z1", address="Dwaraka Nagar, Visakhapatnam", cabins=2),
    dict(name="American Hair Club - Bangalore", code="BLR", city="Bangalore", state="Karnataka",
         state_code="29", gstin="29AAACH1234A1Z8", address="Indiranagar 100ft Road, Bangalore", cabins=2),
]

LEAD_SOURCES = ["Google Ads", "Meta Ads", "Walk-In", "Referral", "WhatsApp", "Website", "Inbound Call"]

LEAD_STATUSES = [
    dict(name="New", extra={"color": "#8A8A93"}),
    dict(name="Contacted", extra={"color": "#5B8DEF"}),
    dict(name="Follow-Up", extra={"color": "#E6A23C"}),
    dict(name="Appointment Booked", extra={"color": "#C9A227"}),
    dict(name="Walk-In", extra={"color": "#9B6BD9"}),
    dict(name="Won", extra={"color": "#3FAE5A", "is_won": True}),
    dict(name="Lost", extra={"color": "#D9534F", "is_lost": True}),
]

HAIR_SIZES = ["7/5", "8/6", "9/6", "9/7", "10/7", "10/8"]
HAIR_MODELS = ["Mono", "Golden-Mono", "Octagon", "Miraj", "Golden Miraj", "Paberia Miraj+",
               "Golden Australia", "Paberia Australia", "Poly", "China Mono",
               "Full Lace (Golden)", "Full Lace (Paberia)", "Front Lace Miraj"]
HAIR_COLORS = ["Natural Black", "Dark Brown", "Salt & Pepper (20%)", "Salt & Pepper (40%)", "Grey"]
HAIR_LENGTHS = ["Short", "Medium", "Long"]
HAIR_DENSITIES = ["Light (80%)", "Medium (100%)", "Heavy (120%)"]
BASE_MATERIALS = ["Mono Base", "Poly Base", "Lace Base", "Skin Base"]

INVENTORY_CATEGORIES = ["Hair Systems", "Adhesives & Tapes", "Scalp Protectors",
                         "Shampoos & Conditioners", "Cleaning Solutions", "Maintenance Kits"]
EXPENSE_CATEGORIES = ["Rent", "Salaries", "Marketing/Ad Spend", "Utilities",
                       "Inventory Purchases", "Maintenance", "Miscellaneous"]
TECH_DESIGNATIONS = ["Senior Hair Technician", "Hair Technician", "Trainee Technician", "Stylist"]

SERVICE_TYPES = [
    dict(name="New Hair Patch Fitting", base_price=25000, sac="999599", overrides={"BLR": 27000}),
    dict(name="Hair System Replacement", base_price=18000, sac="999599", overrides={}),
    dict(name="Maintenance & Cleaning", base_price=1500, sac="999599", overrides={}),
    dict(name="Hair Coloring", base_price=2500, sac="999599", overrides={}),
    dict(name="Hair Wash & Styling", base_price=800, sac="999599", overrides={}),
    dict(name="Bonding/Rebonding", base_price=4000, sac="999599", overrides={}),
]

FIRST_NAMES = ["Ravi", "Suresh", "Kiran", "Anil", "Vijay", "Srinivas", "Praveen", "Naveen", "Ramesh",
               "Mahesh", "Sandeep", "Rajesh", "Manoj", "Ashok", "Venkatesh", "Sathish", "Gopal",
               "Arjun", "Karthik", "Deepak", "Sunil", "Nagesh", "Prasad", "Harish", "Vikram",
               "Chandra", "Bhaskar", "Gowtham", "Aditya", "Rahul", "Sanjay", "Prakash", "Krishna"]
LAST_NAMES = ["Kumar", "Reddy", "Rao", "Sharma", "Naidu", "Chowdary", "Varma", "Gupta", "Iyer",
              "Pillai", "Nair", "Setty", "Prasad", "Murthy", "Patel", "Verma"]


def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_phone():
    return f"+91{random.randint(7000000000, 9999999999)}"


# ---------------------------------------------------------------------------


async def wipe_all():
    for model in ALL_DOCUMENT_MODELS:
        await model.get_motor_collection().delete_many({})


async def seed_branches_and_cabins():
    branches = []
    for b in BRANCHES:
        branch = Branch(name=b["name"], code=b["code"], address=b["address"], city=b["city"],
                         state=b["state"], state_code=b["state_code"], gstin=b["gstin"])
        await branch.insert()
        branches.append(branch)
        for i in range(1, b["cabins"] + 1):
            await Cabin(branch_id=str(branch.id), name=f"Cabin {i}").insert()
    return branches


async def seed_users():
    admin = User(email="admin@americanhairclubs.com", password_hash=hash_password("Admin@123"),
                 name="Founder / Super Admin", role=Role.SUPER_ADMIN, phone="+919000000001")
    manager = User(email="manager@americanhairclubs.com", password_hash=hash_password("Manager@123"),
                   name="Operations Manager", role=Role.MANAGER, phone="+919000000002")
    await admin.insert()
    await manager.insert()
    return admin, manager


async def seed_settings_items():
    items = {}

    async def make_list(list_type, names, extras=None):
        out = []
        for i, n in enumerate(names):
            extra = (extras[i] if extras else {}) or {}
            si = SettingsItem(list_type=list_type, name=n, sort_order=i, extra=extra)
            await si.insert()
            out.append(si)
        items[list_type] = out
        return out

    await make_list("LEAD_SOURCE", LEAD_SOURCES)
    await make_list("LEAD_STATUS", [s["name"] for s in LEAD_STATUSES], [s["extra"] for s in LEAD_STATUSES])
    await make_list("VISIT_REASON", ["New Patch", "Service/Maintenance"])
    await make_list("HAIR_SYSTEM_SIZE", HAIR_SIZES)
    await make_list("HAIR_SYSTEM_MODEL", HAIR_MODELS)
    await make_list("HAIR_COLOR", HAIR_COLORS)
    await make_list("HAIR_LENGTH", HAIR_LENGTHS)
    await make_list("HAIR_DENSITY", HAIR_DENSITIES)
    await make_list("BASE_MATERIAL", BASE_MATERIALS)
    await make_list("INVENTORY_CATEGORY", INVENTORY_CATEGORIES)
    await make_list("EXPENSE_CATEGORY", EXPENSE_CATEGORIES)
    await make_list("TECHNICIAN_DESIGNATION", TECH_DESIGNATIONS)
    return items


async def seed_service_types():
    out = []
    for s in SERVICE_TYPES:
        st = ServiceType(name=s["name"], sac_code=s["sac"], base_price=s["base_price"],
                          branch_price_overrides=s["overrides"], default_gst_rate=18.0)
        await st.insert()
        out.append(st)
    return out


async def seed_message_templates():
    templates = [
        dict(channel="WHATSAPP", name="New Lead Welcome", trigger_event="NEW_LEAD",
             body="Hi {{name}}, thanks for your interest in American Hair Club! Our team will call you shortly.",
             placeholders=["name"]),
        dict(channel="SMS", name="Follow-Up Reminder", trigger_event="FOLLOW_UP_DUE",
             body="Hi {{name}}, this is a reminder about your hair consultation follow-up. Call us at {{branch_phone}}.",
             placeholders=["name", "branch_phone"]),
        dict(channel="WHATSAPP", name="Appointment Reminder", trigger_event="APPOINTMENT_REMINDER",
             body="Hi {{name}}, your appointment at {{branch_name}} is confirmed for {{date}} {{time}}.",
             placeholders=["name", "branch_name", "date", "time"]),
        dict(channel="EMAIL", name="Maintenance Due", trigger_event="MAINTENANCE_DUE", subject="Time for your hair system maintenance",
             body="Hi {{name}}, your hair system is due for maintenance. Book your slot today!",
             placeholders=["name"]),
    ]
    for t in templates:
        await MessageTemplate(**t).insert()


async def seed_technicians(branches):
    designations = await SettingsItem.find(SettingsItem.list_type == "TECHNICIAN_DESIGNATION").to_list()
    techs = []
    for branch in branches:
        count = 3 if branch.code == "HYD" else 2
        for _ in range(count):
            tech = Technician(branch_id=str(branch.id), name=random_name(), phone=random_phone(),
                               designation_id=str(random.choice(designations).id))
            await tech.insert()
            techs.append(tech)
    return techs


async def seed_inventory(branches, items):
    categories = {c.name: c for c in items["INVENTORY_CATEGORY"]}
    catalogue = [
        ("Golden Mono Hair System 8/6", "Hair Systems", 2500, 8),
        ("Miraj Hair System 9/7", "Hair Systems", 3200, 6),
        ("Full Lace Hair System 10/7", "Hair Systems", 4500, 4),
        ("Poly Base Hair System 7/5", "Hair Systems", 1800, 10),
        ("Walker Tape Ultra Hold Roll", "Adhesives & Tapes", 450, 20),
        ("Bonding Glue 60ml", "Adhesives & Tapes", 380, 15),
        ("Double-Sided Adhesive Tabs (pack)", "Adhesives & Tapes", 220, 3),
        ("Liquid Adhesive Remover 250ml", "Adhesives & Tapes", 300, 12),
        ("Scalp Protector Spray", "Scalp Protectors", 550, 9),
        ("Scalp Protector Cream", "Scalp Protectors", 480, 2),
        ("Sulfate-Free Shampoo 250ml", "Shampoos & Conditioners", 650, 18),
        ("Hair System Conditioner 250ml", "Shampoos & Conditioners", 600, 14),
        ("Deep Conditioning Mask", "Shampoos & Conditioners", 750, 7),
        ("Cleaning Solution Concentrate 500ml", "Cleaning Solutions", 900, 11),
        ("Isopropyl Alcohol 500ml", "Cleaning Solutions", 250, 25),
        ("Maintenance Kit - Standard", "Maintenance Kits", 1200, 5),
        ("Maintenance Kit - Premium", "Maintenance Kits", 2100, 3),
        ("Styling Comb Set", "Maintenance Kits", 350, 1),
    ]
    inv_items = []
    for branch in branches:
        for name, cat, cost, base_stock in catalogue:
            stock = max(0, base_stock + random.randint(-3, 4))
            expiry = None
            if cat in ("Shampoos & Conditioners", "Cleaning Solutions", "Adhesives & Tapes"):
                expiry = NOW + timedelta(days=random.choice([20, 40, 400, 500, 600]))
            item = InventoryItem(branch_id=str(branch.id), name=name, category_id=str(categories[cat].id),
                                  sku=f"{branch.code}-{name[:3].upper()}-{random.randint(100,999)}",
                                  stock_qty=stock, reorder_level=5, unit_cost=cost, expiry_date=expiry,
                                  supplier_name=random.choice(["HairPro Supplies", "Vardhan Traders", "Global Hair Imports"]))
            await item.insert()
            inv_items.append(item)
            await InventoryTransaction(branch_id=str(branch.id), item_id=str(item.id),
                                        txn_type=InventoryTxnType.RECEIPT, qty=base_stock,
                                        reference_type="MANUAL", notes="Initial stock load",
                                        created_at=days_ago(90)).insert()

    # Force a couple of items into deliberate low-stock / near-expiry state per branch for demo
    for branch in branches:
        branch_items = [i for i in inv_items if i.branch_id == str(branch.id)]
        low = random.choice(branch_items)
        low.stock_qty = random.choice([0, 1, 2])
        await low.save()
        near_expiry = random.choice(branch_items)
        near_expiry.expiry_date = NOW + timedelta(days=random.randint(5, 25))
        await near_expiry.save()

    # A few purchase orders in different statuses
    for branch, status in zip(branches, [PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.ORDERED,
                                          PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.RECEIVED]):
        sample_items = [i for i in inv_items if i.branch_id == str(branch.id)][:3]
        lines = [{"item_id": str(i.id), "item_name": i.name, "qty": 10, "unit_cost": i.unit_cost} for i in sample_items]
        po = PurchaseOrder(branch_id=str(branch.id), supplier_name="HairPro Supplies", status=status,
                            lines=lines, total_cost=sum(l["qty"] * l["unit_cost"] for l in lines),
                            ordered_at=days_ago(15) if status != PurchaseOrderStatus.DRAFT else None,
                            received_at=days_ago(5) if status == PurchaseOrderStatus.RECEIVED else None)
        await po.insert()

    return inv_items


async def seed_company_config_and_integrations():
    await CompanyConfig(company_name="American Hair Club").insert()
    for provider in ["GOOGLE_ADS", "META_ADS", "WHATSAPP", "SMS", "EMAIL"]:
        await Integration(provider=provider, is_enabled=False).insert()


def month_starts(n_months=12):
    """Return n_months datetimes, one per month, walking back from current month."""
    out = []
    y, m = NOW.year, NOW.month
    for _ in range(n_months):
        out.append(datetime(y, m, 1, tzinfo=timezone.utc))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


async def seed_expenses(branches, cats):
    category_map = {c.name: c for c in cats["EXPENSE_CATEGORY"]}
    months = month_starts(12)
    base_rent = {"HYD": 85000, "PUN": 70000, "VIZ": 55000, "BLR": 95000}
    base_salary = {"HYD": 280000, "PUN": 220000, "VIZ": 180000, "BLR": 260000}
    seasonal = [1.0, 0.95, 1.05, 1.1, 0.9, 0.85, 1.15, 1.2, 1.0, 1.05, 1.3, 1.4]  # trailing 12 months incl festive/year-end bump
    count = 0
    for branch in branches:
        for idx, month_start in enumerate(months):
            factor = seasonal[idx]
            incurred = month_start + timedelta(days=random.randint(0, 4))
            await Expense(branch_id=str(branch.id), category_id=str(category_map["Rent"].id),
                          description=f"Monthly rent - {month_start.strftime('%b %Y')}",
                          amount=round(base_rent[branch.code] * random.uniform(0.98, 1.0)),
                          is_recurring=True, incurred_at=incurred).insert()
            await Expense(branch_id=str(branch.id), category_id=str(category_map["Salaries"].id),
                          description=f"Staff salaries - {month_start.strftime('%b %Y')}",
                          amount=round(base_salary[branch.code] * factor * random.uniform(0.97, 1.03)),
                          is_recurring=True, incurred_at=incurred + timedelta(days=1)).insert()
            await Expense(branch_id=str(branch.id), category_id=str(category_map["Marketing/Ad Spend"].id),
                          description=f"Google/Meta ad spend - {month_start.strftime('%b %Y')}",
                          amount=round(random.uniform(15000, 60000) * factor),
                          is_recurring=True, incurred_at=incurred + timedelta(days=2)).insert()
            await Expense(branch_id=str(branch.id), category_id=str(category_map["Utilities"].id),
                          description=f"Electricity & internet - {month_start.strftime('%b %Y')}",
                          amount=round(random.uniform(6000, 14000)),
                          is_recurring=True, incurred_at=incurred + timedelta(days=3)).insert()
            await Expense(branch_id=str(branch.id), category_id=str(category_map["Inventory Purchases"].id),
                          description=f"Stock replenishment - {month_start.strftime('%b %Y')}",
                          amount=round(random.uniform(20000, 70000) * factor),
                          incurred_at=incurred + timedelta(days=5)).insert()
            if random.random() < 0.6:
                await Expense(branch_id=str(branch.id), category_id=str(category_map["Maintenance"].id),
                              description=random.choice(["AC servicing", "Cabin furniture repair", "Plumbing fix"]),
                              amount=round(random.uniform(2000, 12000)), incurred_at=incurred + timedelta(days=7)).insert()
            if random.random() < 0.5:
                await Expense(branch_id=str(branch.id), category_id=str(category_map["Miscellaneous"].id),
                              description=random.choice(["Office supplies", "Courier charges", "Client refreshments"]),
                              amount=round(random.uniform(1000, 5000)), incurred_at=incurred + timedelta(days=10)).insert()
            count += 6
    return count


async def next_invoice_number_seed(branch_code, issued_at):
    """Local atomic-ish counter for seeding (single-threaded, safe here)."""
    fy_code = financial_year_short_code(issued_at, 4)
    fy_label = financial_year_label(issued_at, 4)
    key = f"INV-{branch_code}-FY{fy_code}"
    counter = await Counter.find_one(Counter.key == key)
    if not counter:
        counter = Counter(key=key, value=0)
    counter.value += 1
    await counter.save()
    return f"AHC/{branch_code}/{fy_code}/{counter.value:04d}", fy_label


async def make_invoice(branch, customer, service_type, technician, service, issued_at, status, gst_rate=18.0):
    gst_type = determine_gst_type(branch.state_code, customer.gst_state_code)
    price = service_type.price_for_branch(branch.code)
    tax = compute_line_tax(price, gst_rate, gst_type)
    line = InvoiceLine(description=service_type.name, hsn_sac_code=service_type.sac_code,
                        service_type_id=str(service_type.id), qty=1, unit_price=price,
                        taxable_value=price, gst_rate=gst_rate, line_total=price + sum(
                            v for k, v in tax.items()), **tax)
    invoice_number, fy_label = await next_invoice_number_seed(branch.code, issued_at)
    grand_total = line.line_total
    if status == InvoiceStatus.PAID:
        amount_paid = grand_total
    elif status == InvoiceStatus.PARTIALLY_PAID:
        amount_paid = round(grand_total * random.uniform(0.3, 0.7), 2)
    elif status == InvoiceStatus.OVERDUE:
        amount_paid = 0
    else:
        amount_paid = 0
    invoice = Invoice(branch_id=str(branch.id), customer_id=str(customer.id), invoice_number=invoice_number,
                       financial_year=fy_label, gst_type=gst_type, lines=[line], subtotal=price,
                       total_cgst=tax["cgst_amount"], total_sgst=tax["sgst_amount"], total_igst=tax["igst_amount"],
                       grand_total=grand_total, amount_paid=amount_paid, status=status,
                       due_date=issued_at + timedelta(days=15), issued_at=issued_at, created_at=issued_at)
    await invoice.insert()
    if amount_paid > 0:
        await Payment(invoice_id=str(invoice.id), branch_id=str(branch.id), amount=amount_paid,
                      method=random.choice(list(PaymentMethod)), paid_at=issued_at + timedelta(days=random.randint(0, 5))).insert()
    service.invoice_id = str(invoice.id)
    await service.save()
    return invoice


async def seed_historical_revenue(branches, service_types, techs_by_branch, settings_items):
    """Populate 12 months of customers/services/invoices so profit charts have real trend data."""
    months = month_starts(12)
    volume_factor = [8, 7, 9, 10, 6, 5, 11, 12, 9, 10, 14, 16]  # invoices/branch/month, seasonal dip mid-year, festive ramp
    hair_models = settings_items["HAIR_SYSTEM_MODEL"]
    hair_sizes = settings_items["HAIR_SYSTEM_SIZE"]
    hair_colors = settings_items["HAIR_COLOR"]
    hair_lengths = settings_items["HAIR_LENGTH"]
    hair_densities = settings_items["HAIR_DENSITY"]
    base_materials = settings_items["BASE_MATERIAL"]

    total_invoices = 0
    for branch in branches:
        for idx, month_start in enumerate(months):
            n = volume_factor[idx] + random.randint(-2, 2)
            for _ in range(max(3, n)):
                day_offset = random.randint(0, 26)
                issued_at = month_start + timedelta(days=day_offset, hours=random.randint(9, 18))
                customer = Customer(branch_id=str(branch.id), name=random_name(), phone=random_phone(),
                                     email=None, gst_state_code=branch.state_code if random.random() > 0.1 else None,
                                     created_at=issued_at)
                await customer.insert()
                technician = random.choice(techs_by_branch[branch.code])
                service_type = random.choice(service_types)
                is_new_patch = service_type.name == "New Hair Patch Fitting"
                service = Service(branch_id=str(branch.id), customer_id=str(customer.id),
                                   technician_id=str(technician.id), service_type_id=str(service_type.id),
                                   visit_reason=VisitReasonType.NEW_PATCH if is_new_patch else VisitReasonType.SERVICE,
                                   price_charged=service_type.price_for_branch(branch.code),
                                   performed_at=issued_at, created_at=issued_at)
                await service.insert()
                if is_new_patch:
                    await HairSystemInstallation(
                        branch_id=str(branch.id), customer_id=str(customer.id), technician_id=str(technician.id),
                        service_id=str(service.id), hair_system_model_id=str(random.choice(hair_models).id),
                        hair_system_size_id=str(random.choice(hair_sizes).id),
                        hair_color_id=str(random.choice(hair_colors).id),
                        hair_length_id=str(random.choice(hair_lengths).id),
                        hair_density_id=str(random.choice(hair_densities).id),
                        base_material_id=str(random.choice(base_materials).id),
                        installed_at=issued_at, next_maintenance_due=issued_at + timedelta(days=45),
                    ).insert()
                status = random.choices(
                    [InvoiceStatus.PAID, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE],
                    weights=[0.75, 0.15, 0.10])[0]
                await make_invoice(branch, customer, service_type, technician, service, issued_at, status)
                total_invoices += 1
    return total_invoices


async def seed_leads_pipeline(branches, settings_items, users):
    sources = settings_items["LEAD_SOURCE"]
    statuses = {s.name: s for s in settings_items["LEAD_STATUS"]}
    status_cycle = ["New", "Contacted", "Follow-Up", "Appointment Booked", "Walk-In", "Won", "Lost"]
    campaigns = ["Monsoon Hair Offer", "New Year Confidence Campaign", "Festive Season Special", "Referral Boost"]
    admin, manager = users

    leads_created = []
    total = 34  # >= 30
    for i in range(total):
        branch = branches[i % len(branches)]
        status_name = status_cycle[i % len(status_cycle)]
        source = random.choice(sources)
        created_at = days_ago(random.randint(1, 45))
        has_attribution = source.name in ("Google Ads", "Meta Ads") and random.random() < 0.8
        lead = Lead(
            branch_id=str(branch.id), name=random_name(), phone=random_phone(),
            email=None, lead_source_id=str(source.id), lead_status_id=str(statuses[status_name].id),
            visit_reason=random.choice([VisitReasonType.NEW_PATCH, VisitReasonType.SERVICE]),
            assigned_to_user_id=str(manager.id),
            campaign_name=random.choice(campaigns) if has_attribution else None,
            utm_source=source.name.lower().replace(" ", "_") if has_attribution else None,
            utm_medium="cpc" if has_attribution else None,
            utm_campaign=random.choice(campaigns).lower().replace(" ", "_") if has_attribution else None,
            created_at=created_at, updated_at=created_at,
        )
        if status_name == "Won":
            lead.converted_at = created_at + timedelta(days=random.randint(1, 5))
        if status_name == "Lost":
            lead.lost_reason = random.choice(["Too expensive", "Chose competitor", "No longer interested"])
        await lead.insert()
        leads_created.append(lead)

        await LeadActivity(lead_id=str(lead.id), branch_id=str(branch.id), activity_type="SYSTEM",
                            description=f"Lead created via {source.name}", performed_by_user_id=str(manager.id),
                            created_at=created_at).insert()

        # calls + follow-ups for a realistic spread
        if status_name not in ("New",):
            call_time = created_at + timedelta(hours=random.randint(2, 30))
            await Call(lead_id=str(lead.id), branch_id=str(branch.id), direction="OUTBOUND",
                       phone=lead.phone, outcome=random.choice(list(CallOutcome)),
                       duration_seconds=random.randint(30, 400), performed_by_user_id=str(manager.id),
                       called_at=call_time).insert()
            await LeadActivity(lead_id=str(lead.id), branch_id=str(branch.id), activity_type="CALL",
                                description="Outbound call logged", performed_by_user_id=str(manager.id),
                                created_at=call_time).insert()

        if status_name in ("Follow-Up", "Contacted", "Appointment Booked"):
            due = NOW + timedelta(days=random.randint(-3, 5))  # mix of overdue and upcoming
            await FollowUp(lead_id=str(lead.id), branch_id=str(branch.id), due_date=due,
                           status=FollowUpStatus.PENDING if due > NOW - timedelta(days=1) or random.random() < 0.5 else FollowUpStatus.DONE,
                           notes="Discuss hair system options and pricing", assigned_to_user_id=str(manager.id),
                           created_at=created_at).insert()

    # Guarantee at least one clear example in each follow-up bucket for demo purposes,
    # each with a name/phone/notes and a couple of comments so the UI isn't empty.
    demo_examples = [
        ("Overdue Example — Priya Sharma", "+919876543210", NOW - timedelta(days=3),
         "Interested in New Hair Patch Fitting, wanted a callback about pricing.",
         [("Called once, no answer.", manager), ("Tried WhatsApp, will retry.", admin)]),
        ("Today Example — Arjun Reddy", "+919876543211", NOW,
         "Confirmed interested, wants to visit branch this week.",
         [("Spoke yesterday, confirmed interest.", manager)]),
        ("Upcoming Example — Kavya Nair", "+919876543212", NOW + timedelta(days=4),
         "Asked to be contacted after payday for a New Hair Patch Fitting quote.",
         []),
    ]
    demo_branch = branches[0]
    demo_source = sources[0]
    demo_status = statuses["Follow-Up"]
    for name, phone, due, notes, comments in demo_examples:
        demo_lead = Lead(
            branch_id=str(demo_branch.id), name=name, phone=phone, email=None,
            lead_source_id=str(demo_source.id), lead_status_id=str(demo_status.id),
            visit_reason=VisitReasonType.NEW_PATCH, assigned_to_user_id=str(manager.id),
            created_at=days_ago(2), updated_at=days_ago(2),
        )
        await demo_lead.insert()
        leads_created.append(demo_lead)
        await LeadActivity(lead_id=str(demo_lead.id), branch_id=str(demo_branch.id), activity_type="SYSTEM",
                            description="Lead created (demo example)", created_at=days_ago(2)).insert()
        fu = FollowUp(
            lead_id=str(demo_lead.id), branch_id=str(demo_branch.id), due_date=due, notes=notes,
            assigned_to_user_id=str(manager.id),
            comments=[{"text": text, "created_at": days_ago(1).isoformat(), "user_id": str(u.id), "user_name": u.name}
                      for text, u in comments],
        )
        await fu.insert()

    return leads_created


async def seed_ad_campaigns(branches):
    months = month_starts(3)
    for branch in branches:
        for platform in ["GOOGLE_ADS", "META_ADS"]:
            for month_start in months:
                spend = round(random.uniform(15000, 50000), 2)
                leads_gen = random.randint(15, 60)
                conversions = max(1, int(leads_gen * random.uniform(0.15, 0.35)))
                await AdCampaign(
                    branch_id=str(branch.id), platform=platform,
                    campaign_name=f"{branch.code}-{platform}-{month_start.strftime('%b%Y')}",
                    external_campaign_id=f"ext-{random.randint(100000,999999)}",
                    spend=spend, impressions=random.randint(5000, 40000),
                    clicks=random.randint(200, 2000), leads_generated=leads_gen, conversions=conversions,
                    period_start=month_start, period_end=month_start + timedelta(days=27),
                    last_synced_at=NOW - timedelta(hours=random.randint(1, 48)),
                ).insert()


async def seed_notifications(branches, users):
    admin, manager = users
    kinds = [
        ("NEW_LEAD", "New lead received", "A new lead came in from Google Ads"),
        ("OVERDUE_FOLLOW_UP", "Overdue follow-up", "You have an overdue follow-up to complete"),
        ("LOW_STOCK", "Low stock alert", "Scalp Protector Cream is running low"),
        ("UPCOMING_APPOINTMENT", "Appointment in 1 hour", "You have an upcoming appointment"),
    ]
    for user in (admin, manager):
        for kind, title, msg in kinds:
            await Notification(user_id=str(user.id), type=kind, title=title, message=msg,
                                is_read=random.random() < 0.4, created_at=days_ago(random.randint(0, 5))).insert()


async def run(keep_existing: bool):
    settings = get_settings()
    client = AsyncIOMotorClient(settings.MONGO_URI)
    db = client[settings.MONGO_DB_NAME]
    await init_beanie(database=db, document_models=ALL_DOCUMENT_MODELS)

    if not keep_existing:
        print("Wiping existing collections...")
        await wipe_all()
    else:
        existing = await Branch.find_all().count()
        if existing:
            print("Data already present and --keep passed; skipping seed.")
            return

    print("Seeding branches & cabins...")
    branches = await seed_branches_and_cabins()

    print("Seeding users...")
    users = await seed_users()

    print("Seeding settings entities...")
    settings_items = await seed_settings_items()

    print("Seeding service types...")
    service_types = await seed_service_types()

    print("Seeding message templates...")
    await seed_message_templates()

    print("Seeding technicians...")
    techs = await seed_technicians(branches)
    techs_by_branch = {}
    for t in techs:
        branch_code = next(b.code for b in branches if str(b.id) == t.branch_id)
        techs_by_branch.setdefault(branch_code, []).append(t)

    print("Seeding inventory...")
    await seed_inventory(branches, settings_items)

    print("Seeding company config & integrations...")
    await seed_company_config_and_integrations()

    print("Seeding 12 months of expenses...")
    n_exp = await seed_expenses(branches, settings_items)
    print(f"  -> {n_exp} expenses created")

    print("Seeding 12 months of customers/services/invoices (this drives the profit charts)...")
    n_inv = await seed_historical_revenue(branches, service_types, techs_by_branch, settings_items)
    print(f"  -> {n_inv} invoices created")

    print("Seeding lead pipeline (30+ leads across stages/sources/branches)...")
    await seed_leads_pipeline(branches, settings_items, users)

    print("Seeding ad campaigns...")
    await seed_ad_campaigns(branches)

    print("Seeding notifications...")
    await seed_notifications(branches, users)

    print("\nSeed complete.")
    print("Login credentials:")
    print("  Super Admin:  admin@americanhairclubs.com / Admin@123")
    print("  Manager:      manager@americanhairclubs.com / Manager@123")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="Skip seeding if data already exists")
    args = parser.parse_args()
    asyncio.run(run(keep_existing=args.keep))
PYEOF_2
echo "  wrote backend/seed.py"

mkdir -p "$(dirname "frontend/src/pages/AppointmentsPage.tsx")"
cat > "frontend/src/pages/AppointmentsPage.tsx" << 'PYEOF_3'
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import { Modal } from "@/components/shared/Modal";
import { BookAppointmentForm } from "@/components/appointments/BookAppointmentForm";
import { Plus } from "lucide-react";

interface Appointment {
  id: string;
  cabin_id: string;
  start_time: string;
  end_time: string;
  status: string;
  visit_reason: string;
}

interface Cabin { id: string; name: string; }

const STATUS_COLORS: Record<string, string> = {
  BOOKED: "text-neutral-300 bg-charcoal-700",
  CONFIRMED: "text-blue-300 bg-blue-950/40",
  IN_PROGRESS: "text-amber-300 bg-amber-950/40",
  COMPLETED: "text-emerald-300 bg-emerald-950/40",
  NO_SHOW: "text-red-300 bg-red-950/40",
  CANCELLED: "text-neutral-500 bg-neutral-900/60",
};

export default function AppointmentsPage() {
  const { branches } = useBranch();
  const [activeBranchId, setActiveBranchId] = useState<string | null>(null);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [showBookModal, setShowBookModal] = useState(false);

  const branchId = activeBranchId ?? branches[0]?.id ?? null;
  const activeBranch = branches.find((b) => b.id === branchId);

  const { data: cabins } = useQuery({
    queryKey: ["cabins", branchId],
    queryFn: async () => (await api.get<Cabin[]>("/branches/cabins", { params: { branch_id: branchId } })).data,
    enabled: !!branchId,
  });

  const dayStart = new Date(`${date}T00:00:00`);
  const dayEnd = new Date(`${date}T23:59:59`);

  const { data: appointments } = useQuery({
    queryKey: ["appointments", branchId, date],
    queryFn: async () =>
      (await api.get<Appointment[]>("/appointments", {
        params: { branch_id: branchId, date_from: dayStart.toISOString(), date_to: dayEnd.toISOString() },
      })).data,
    enabled: !!branchId,
  });

  if (branches.length === 0) {
    return <div className="text-neutral-500 text-sm">Loading branches…</div>;
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex gap-2">
          {branches.map((b) => (
            <button
              key={b.id}
              onClick={() => setActiveBranchId(b.id)}
              className={`px-4 py-1.5 rounded-full text-sm transition ${
                branchId === b.id ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
              }`}
            >
              {b.name}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <input type="date" className="input-field" value={date} onChange={(e) => setDate(e.target.value)} />
          <button onClick={() => setShowBookModal(true)} className="btn-gold flex items-center gap-2 text-sm">
            <Plus size={16} /> Book Slot
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {(cabins ?? []).map((cabin) => {
          const cabinAppts = (appointments ?? [])
            .filter((a) => a.cabin_id === cabin.id)
            .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
          return (
            <div key={cabin.id} className="card p-4">
              <h3 className="font-display text-lg text-gold-light mb-3">{cabin.name}</h3>
              <div className="space-y-2">
                {cabinAppts.length === 0 && <div className="text-xs text-neutral-600">No bookings for this day.</div>}
                {cabinAppts.map((a) => (
                  <div key={a.id} className="bg-charcoal-700 rounded-lg px-3 py-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-neutral-200">
                        {new Date(a.start_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                        {" – "}
                        {new Date(a.end_time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                      </span>
                      <span className={`px-2 py-0.5 rounded-full ${STATUS_COLORS[a.status] ?? ""}`}>{a.status}</span>
                    </div>
                    <div className="text-neutral-500 mt-1">
                      {a.visit_reason === "NEW_PATCH" ? "New Patch" : "Service / Maintenance"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
        {(cabins ?? []).length === 0 && (
          <div className="text-neutral-600 text-sm col-span-full">No cabins configured for this branch yet.</div>
        )}
      </div>

      <Modal open={showBookModal} onClose={() => setShowBookModal(false)} title={`Book Slot — ${activeBranch?.name ?? ""}`}>
        {activeBranch && <BookAppointmentForm branch={activeBranch} onDone={() => setShowBookModal(false)} />}
      </Modal>
    </div>
  );
}
PYEOF_3
echo "  wrote frontend/src/pages/AppointmentsPage.tsx"

mkdir -p "$(dirname "frontend/src/components/appointments/BookAppointmentForm.tsx")"
cat > "frontend/src/components/appointments/BookAppointmentForm.tsx" << 'PYEOF_4'
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Branch, Customer } from "@/types";

interface Cabin { id: string; name: string; }
interface Technician { id: string; name: string; }

const VISIT_REASONS = [
  { value: "NEW_PATCH", label: "New Patch" },
  { value: "SERVICE", label: "Service / Maintenance" },
];

const DURATIONS = [
  { minutes: 60, label: "1 hour" },
  { minutes: 90, label: "1.5 hours" },
  { minutes: 120, label: "2 hours" },
];

export function BookAppointmentForm({ branch, onDone }: { branch: Branch; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    cabin_id: "",
    customer_id: "",
    technician_id: "",
    visit_reason: "NEW_PATCH",
    date: new Date().toISOString().slice(0, 10),
    time: "10:00",
    duration: 90,
    notes: "",
  });
  const [customerSearch, setCustomerSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: cabins } = useQuery({
    queryKey: ["cabins", branch.id],
    queryFn: async () => (await api.get<Cabin[]>("/branches/cabins", { params: { branch_id: branch.id } })).data,
  });

  const { data: technicians } = useQuery({
    queryKey: ["technicians", branch.id],
    queryFn: async () => (await api.get<Technician[]>("/technicians", { params: { branch_id: branch.id } })).data,
  });

  const { data: customers } = useQuery({
    queryKey: ["customers", branch.id, customerSearch],
    queryFn: async () =>
      (await api.get<Customer[]>("/customers", {
        params: { branch_id: branch.id, ...(customerSearch ? { search: customerSearch } : {}) },
      })).data,
  });

  const createAppointment = useMutation({
    mutationFn: async () => {
      const start = new Date(`${form.date}T${form.time}:00`);
      const end = new Date(start.getTime() + form.duration * 60000);
      return api.post("/appointments", {
        branch_id: branch.id,
        cabin_id: form.cabin_id,
        customer_id: form.customer_id || null,
        technician_id: form.technician_id || null,
        visit_reason: form.visit_reason,
        start_time: start.toISOString(),
        end_time: end.toISOString(),
        notes: form.notes || null,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["appointments"] });
      onDone();
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? "Could not create booking"),
  });

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        if (!form.cabin_id) { setError("Please select a cabin."); return; }
        createAppointment.mutate();
      }}
      className="space-y-3"
    >
      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Cabin</label>
        <select className="input-field w-full" value={form.cabin_id} onChange={(e) => set("cabin_id", e.target.value)} required>
          <option value="">Select cabin…</option>
          {(cabins ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Date</label>
          <input type="date" className="input-field w-full" value={form.date} onChange={(e) => set("date", e.target.value)} required />
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Start Time</label>
          <input type="time" className="input-field w-full" value={form.time} onChange={(e) => set("time", e.target.value)} required />
        </div>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Duration</label>
        <select className="input-field w-full" value={form.duration} onChange={(e) => set("duration", Number(e.target.value))}>
          {DURATIONS.map((d) => <option key={d.minutes} value={d.minutes}>{d.label}</option>)}
        </select>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Customer (optional — search by name/phone)</label>
        <input
          className="input-field w-full mb-1" placeholder="Search customer…"
          value={customerSearch} onChange={(e) => setCustomerSearch(e.target.value)}
        />
        <select className="input-field w-full" value={form.customer_id} onChange={(e) => set("customer_id", e.target.value)}>
          <option value="">No customer linked</option>
          {(customers ?? []).map((c) => <option key={c.id} value={c.id}>{c.name} — {c.phone}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Technician</label>
          <select className="input-field w-full" value={form.technician_id} onChange={(e) => set("technician_id", e.target.value)}>
            <option value="">Unassigned</option>
            {(technicians ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Visit Reason</label>
          <select className="input-field w-full" value={form.visit_reason} onChange={(e) => set("visit_reason", e.target.value)}>
            {VISIT_REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Notes (optional)</label>
        <textarea className="input-field w-full" rows={2} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
      </div>

      {error && <div className="text-sm text-red-400 bg-red-950/30 border border-red-900/50 rounded-lg px-3 py-2">{error}</div>}

      <button type="submit" disabled={createAppointment.isPending} className="btn-gold w-full disabled:opacity-60">
        {createAppointment.isPending ? "Booking…" : "Book Slot"}
      </button>
    </form>
  );
}
PYEOF_4
echo "  wrote frontend/src/components/appointments/BookAppointmentForm.tsx"

mkdir -p "$(dirname "frontend/src/pages/CustomersPage.tsx")"
cat > "frontend/src/pages/CustomersPage.tsx" << 'PYEOF_5'
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import type { Customer } from "@/types";
import { Search } from "lucide-react";

export default function CustomersPage() {
  const { branches } = useBranch();
  const [activeBranchId, setActiveBranchId] = useState<string | "ALL">("ALL");
  const [search, setSearch] = useState("");

  const { data: customers, isLoading } = useQuery({
    queryKey: ["customers", activeBranchId, search],
    queryFn: async () =>
      (await api.get<Customer[]>("/customers", {
        params: { ...(activeBranchId !== "ALL" ? { branch_id: activeBranchId } : {}), ...(search ? { search } : {}) },
      })).data,
  });

  const branchName = (id: string) => branches.find((b) => b.id === id)?.name ?? id;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setActiveBranchId("ALL")}
            className={`px-4 py-1.5 rounded-full text-sm transition ${
              activeBranchId === "ALL" ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
            }`}
          >
            All Branches
          </button>
          {branches.map((b) => (
            <button
              key={b.id}
              onClick={() => setActiveBranchId(b.id)}
              className={`px-4 py-1.5 rounded-full text-sm transition ${
                activeBranchId === b.id ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
              }`}
            >
              {b.name}
            </button>
          ))}
        </div>

        <div className="relative max-w-xs w-full">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" />
          <input
            className="input-field w-full pl-9"
            placeholder="Search by name or phone…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
              <th className="px-4 py-3 font-medium">Name</th>
              <th className="px-4 py-3 font-medium">Branch</th>
              <th className="px-4 py-3 font-medium">Phone</th>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Joined</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-600">Loading…</td></tr>
            )}
            {(customers ?? []).map((c) => (
              <tr key={c.id} className="border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition">
                <td className="px-4 py-3">
                  <Link to={`/customers/${c.id}`} className="text-gold-light hover:underline">{c.name}</Link>
                </td>
                <td className="px-4 py-3 text-neutral-400">{branchName(c.branch_id)}</td>
                <td className="px-4 py-3 text-neutral-400">{c.phone}</td>
                <td className="px-4 py-3 text-neutral-400">{c.email ?? "—"}</td>
                <td className="px-4 py-3 text-neutral-500">{new Date(c.created_at).toLocaleDateString("en-IN")}</td>
              </tr>
            ))}
            {!isLoading && (customers ?? []).length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-600">No customers found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
PYEOF_5
echo "  wrote frontend/src/pages/CustomersPage.tsx"

mkdir -p "$(dirname "frontend/src/pages/InventoryPage.tsx")"
cat > "frontend/src/pages/InventoryPage.tsx" << 'PYEOF_6'
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import { AlertTriangle } from "lucide-react";

interface InventoryItem {
  id: string;
  name: string;
  stock_qty: number;
  reorder_level: number;
  unit: string;
  unit_cost: number;
  expiry_date?: string | null;
}

export default function InventoryPage() {
  const { branches } = useBranch();
  const [activeBranchId, setActiveBranchId] = useState<string | "ALL">("ALL");

  const { data: items, isLoading } = useQuery({
    queryKey: ["inventory", activeBranchId],
    queryFn: async () =>
      (await api.get<InventoryItem[]>("/inventory/items", {
        params: activeBranchId !== "ALL" ? { branch_id: activeBranchId } : {},
      })).data,
  });

  const lowStock = (items ?? []).filter((i) => i.stock_qty <= i.reorder_level);

  return (
    <div>
      <div className="flex gap-2 flex-wrap mb-4">
        <button
          onClick={() => setActiveBranchId("ALL")}
          className={`px-4 py-1.5 rounded-full text-sm transition ${
            activeBranchId === "ALL" ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
          }`}
        >
          All Branches
        </button>
        {branches.map((b) => (
          <button
            key={b.id}
            onClick={() => setActiveBranchId(b.id)}
            className={`px-4 py-1.5 rounded-full text-sm transition ${
              activeBranchId === b.id ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
            }`}
          >
            {b.name}
          </button>
        ))}
      </div>

      {lowStock.length > 0 && (
        <div className="card p-4 mb-6 border-amber-800/60 bg-amber-950/20 flex items-center gap-3">
          <AlertTriangle size={18} className="text-amber-400 shrink-0" />
          <div className="text-sm text-amber-200">
            {lowStock.length} item{lowStock.length > 1 ? "s" : ""} at or below reorder level.
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
              <th className="px-4 py-3 font-medium">Item</th>
              <th className="px-4 py-3 font-medium">Stock</th>
              <th className="px-4 py-3 font-medium">Reorder Level</th>
              <th className="px-4 py-3 font-medium">Unit Cost</th>
              <th className="px-4 py-3 font-medium">Expiry</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-600">Loading…</td></tr>}
            {(items ?? []).map((item) => {
              const low = item.stock_qty <= item.reorder_level;
              return (
                <tr key={item.id} className={`border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition ${low ? "bg-red-950/10" : ""}`}>
                  <td className="px-4 py-3 text-neutral-200">{item.name}</td>
                  <td className={`px-4 py-3 ${low ? "text-red-400 font-medium" : "text-neutral-300"}`}>
                    {item.stock_qty} {item.unit}
                  </td>
                  <td className="px-4 py-3 text-neutral-500">{item.reorder_level}</td>
                  <td className="px-4 py-3 text-neutral-400">₹{item.unit_cost}</td>
                  <td className="px-4 py-3 text-neutral-500">
                    {item.expiry_date ? new Date(item.expiry_date).toLocaleDateString("en-IN") : "—"}
                  </td>
                </tr>
              );
            })}
            {!isLoading && (items ?? []).length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-neutral-600">No inventory items found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
PYEOF_6
echo "  wrote frontend/src/pages/InventoryPage.tsx"

mkdir -p "$(dirname "frontend/src/pages/InvoicesPage.tsx")"
cat > "frontend/src/pages/InvoicesPage.tsx" << 'PYEOF_7'
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import type { Invoice } from "@/types";

const inr = (n: number) => `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

const statusColors: Record<string, string> = {
  PAID: "text-emerald-400 bg-emerald-950/40",
  PARTIALLY_PAID: "text-amber-400 bg-amber-950/40",
  OVERDUE: "text-red-400 bg-red-950/40",
  DRAFT: "text-neutral-400 bg-neutral-800/60",
  CANCELLED: "text-neutral-500 bg-neutral-900/60",
};

export default function InvoicesPage() {
  const { branches } = useBranch();
  const [activeBranchId, setActiveBranchId] = useState<string | "ALL">("ALL");

  const { data: invoices, isLoading } = useQuery({
    queryKey: ["invoices", activeBranchId],
    queryFn: async () =>
      (await api.get<Invoice[]>("/invoices", {
        params: activeBranchId !== "ALL" ? { branch_id: activeBranchId } : {},
      })).data,
  });

  const branchName = (id: string) => branches.find((b) => b.id === id)?.name ?? id;
  const totalOutstanding = (invoices ?? []).reduce((sum, i) => sum + (i.grand_total - i.amount_paid), 0);

  return (
    <div>
      <div className="flex gap-2 flex-wrap mb-4">
        <button
          onClick={() => setActiveBranchId("ALL")}
          className={`px-4 py-1.5 rounded-full text-sm transition ${
            activeBranchId === "ALL" ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
          }`}
        >
          All Branches
        </button>
        {branches.map((b) => (
          <button
            key={b.id}
            onClick={() => setActiveBranchId(b.id)}
            className={`px-4 py-1.5 rounded-full text-sm transition ${
              activeBranchId === b.id ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
            }`}
          >
            {b.name}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="card p-4">
          <div className="text-xs text-neutral-500">Total Invoices</div>
          <div className="kpi-value">{invoices?.length ?? 0}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-neutral-500">Outstanding Balance</div>
          <div className="kpi-value">{inr(totalOutstanding)}</div>
        </div>
        <div className="card p-4">
          <div className="text-xs text-neutral-500">Total Revenue (shown)</div>
          <div className="kpi-value">{inr((invoices ?? []).reduce((s, i) => s + i.grand_total, 0))}</div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
              <th className="px-4 py-3 font-medium">Invoice #</th>
              <th className="px-4 py-3 font-medium">Branch</th>
              <th className="px-4 py-3 font-medium">FY</th>
              <th className="px-4 py-3 font-medium">Issued</th>
              <th className="px-4 py-3 font-medium">Total</th>
              <th className="px-4 py-3 font-medium">Balance</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={7} className="px-4 py-6 text-center text-neutral-600">Loading…</td></tr>}
            {(invoices ?? []).map((inv) => (
              <tr key={inv.id} className="border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition">
                <td className="px-4 py-3 text-gold-light">{inv.invoice_number}</td>
                <td className="px-4 py-3 text-neutral-400">{branchName(inv.branch_id)}</td>
                <td className="px-4 py-3 text-neutral-500">{inv.financial_year}</td>
                <td className="px-4 py-3 text-neutral-400">{new Date(inv.issued_at).toLocaleDateString("en-IN")}</td>
                <td className="px-4 py-3">{inr(inv.grand_total)}</td>
                <td className="px-4 py-3 text-neutral-400">{inr(inv.grand_total - inv.amount_paid)}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-1 rounded-full ${statusColors[inv.status] ?? ""}`}>
                    {inv.status.replaceAll("_", " ")}
                  </span>
                </td>
              </tr>
            ))}
            {!isLoading && (invoices ?? []).length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-neutral-600">No invoices found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
PYEOF_7
echo "  wrote frontend/src/pages/InvoicesPage.tsx"

mkdir -p "$(dirname "frontend/src/pages/TodayDashboardPage.tsx")"
cat > "frontend/src/pages/TodayDashboardPage.tsx" << 'PYEOF_8'
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useBranch } from "@/context/BranchContext";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { ProfitTrendChart } from "@/components/dashboard/ProfitTrendChart";
import { IndianRupee, Users, Footprints, CheckCircle2, Phone, Clock } from "lucide-react";
import type { Lead } from "@/types";

const inr = (n: number) => `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

interface FollowUp {
  id: string;
  due_date: string;
  notes?: string | null;
  lead_id?: string | null;
  customer_id?: string | null;
}

function isToday(dateStr: string) {
  const d = new Date(dateStr);
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

export default function TodayDashboardPage() {
  const { branches } = useBranch();
  const [activeBranchId, setActiveBranchId] = useState<string | "ALL">("ALL");

  const { data: today, isLoading } = useQuery({
    queryKey: ["dashboard", "today"],
    queryFn: async () => (await api.get("/dashboard/today")).data,
  });

  const { data: ops } = useQuery({
    queryKey: ["dashboard", "daily-operations"],
    queryFn: async () => (await api.get("/dashboard/daily-operations")).data,
  });

  const { data: allLeads } = useQuery({
    queryKey: ["leads", activeBranchId, "today-view"],
    queryFn: async () =>
      (await api.get<Lead[]>("/leads", { params: activeBranchId !== "ALL" ? { branch_id: activeBranchId } : {} })).data,
  });

  const { data: followUps } = useQuery({
    queryKey: ["follow-ups", activeBranchId, "today-view"],
    queryFn: async () =>
      (await api.get<FollowUp[]>("/follow-ups", {
        params: { bucket: "today", ...(activeBranchId !== "ALL" ? { branch_id: activeBranchId } : {}) },
      })).data,
  });

  const todaysLeads = useMemo(() => (allLeads ?? []).filter((l) => isToday(l.created_at)), [allLeads]);

  const branchRows = branches.map((b) => {
    const rev = (today?.revenue_by_branch ?? []).find((r: any) => r._id === b.id);
    const leads = (today?.leads_by_branch ?? []).find((r: any) => r._id === b.id);
    const walkins = (today?.walkins_by_branch ?? []).find((r: any) => r._id === b.id);
    return {
      id: b.id, name: b.name,
      revenue: rev?.revenue ?? 0, invoiceCount: rev?.invoice_count ?? 0,
      leads: leads?.count ?? 0, walkins: walkins?.count ?? 0,
    };
  });

  const selectedRow = activeBranchId !== "ALL" ? branchRows.find((r) => r.id === activeBranchId) : null;

  return (
    <div className="space-y-8">
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setActiveBranchId("ALL")}
          className={`px-4 py-1.5 rounded-full text-sm transition ${
            activeBranchId === "ALL" ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
          }`}
        >
          All Branches
        </button>
        {branches.map((b) => (
          <button
            key={b.id}
            onClick={() => setActiveBranchId(b.id)}
            className={`px-4 py-1.5 rounded-full text-sm transition ${
              activeBranchId === b.id ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
            }`}
          >
            {b.name}
          </button>
        ))}
      </div>

      <section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard
            label="Revenue Today"
            value={isLoading ? "…" : inr(selectedRow ? selectedRow.revenue : today?.total_revenue_today ?? 0)}
            icon={<IndianRupee size={18} />}
          />
          <KpiCard
            label="Leads Today"
            value={isLoading ? "…" : String(selectedRow ? selectedRow.leads : today?.leads_today ?? 0)}
            icon={<Users size={18} />}
          />
          <KpiCard
            label="Walk-Ins Today"
            value={isLoading ? "…" : String(selectedRow ? selectedRow.walkins : today?.walk_ins_today ?? 0)}
            icon={<Footprints size={18} />}
          />
          <KpiCard
            label="Conversions Today"
            value={isLoading ? "…" : String(today?.conversions_today ?? 0)}
            icon={<CheckCircle2 size={18} />}
          />
        </div>
      </section>

      {activeBranchId === "ALL" && branches.length > 0 && (
        <section>
          <h2 className="font-display text-lg text-neutral-200 mb-3">Today — By Branch</h2>
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-neutral-500 border-b border-charcoal-border">
                  <th className="px-4 py-3 font-medium">Branch</th>
                  <th className="px-4 py-3 font-medium">Revenue</th>
                  <th className="px-4 py-3 font-medium">Invoices</th>
                  <th className="px-4 py-3 font-medium">New Leads</th>
                  <th className="px-4 py-3 font-medium">Walk-Ins</th>
                </tr>
              </thead>
              <tbody>
                {branchRows.map((row) => (
                  <tr key={row.id} className="border-b border-charcoal-border/60 hover:bg-charcoal-700/40 transition">
                    <td className="px-4 py-3 text-neutral-200">{row.name}</td>
                    <td className="px-4 py-3 text-gold-light">{inr(row.revenue)}</td>
                    <td className="px-4 py-3 text-neutral-400">{row.invoiceCount}</td>
                    <td className="px-4 py-3 text-neutral-400">{row.leads}</td>
                    <td className="px-4 py-3 text-neutral-400">{row.walkins}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section>
          <h2 className="font-display text-lg text-neutral-200 mb-3 flex items-center gap-2">
            <Users size={16} className="text-gold-light" /> Today's Leads ({todaysLeads.length})
          </h2>
          <div className="card divide-y divide-charcoal-border max-h-96 overflow-y-auto">
            {todaysLeads.length === 0 && <div className="p-4 text-neutral-600 text-sm">No leads created today yet.</div>}
            {todaysLeads.map((l) => (
              <div key={l.id} className="px-4 py-3">
                <div className="text-sm text-neutral-200">{l.name}</div>
                <div className="flex items-center gap-1.5 text-xs text-neutral-500 mt-1">
                  <Phone size={11} /> {l.phone}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="font-display text-lg text-neutral-200 mb-3 flex items-center gap-2">
            <Clock size={16} className="text-gold-light" /> Today's Follow-Ups ({(followUps ?? []).length})
          </h2>
          <div className="card divide-y divide-charcoal-border max-h-96 overflow-y-auto">
            {(followUps ?? []).length === 0 && <div className="p-4 text-neutral-600 text-sm">No follow-ups due today.</div>}
            {(followUps ?? []).map((fu) => (
              <div key={fu.id} className="px-4 py-3">
                <div className="text-sm text-neutral-200">{fu.notes ?? "Follow-up"}</div>
                <div className="text-xs text-neutral-500 mt-1">
                  Due {new Date(fu.due_date).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section>
        <h2 className="font-display text-lg text-neutral-200 mb-3">12-Month Profit Trend</h2>
        <div className="card p-6">
          <ProfitTrendChart branchId={activeBranchId !== "ALL" ? activeBranchId : undefined} />
        </div>
      </section>

      {ops && activeBranchId === "ALL" && (
        <section>
          <h2 className="font-display text-lg text-neutral-200 mb-3">Daily Operations (All Branches)</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {Object.entries(ops).map(([key, value]) => (
              <div key={key} className="card p-4">
                <div className="text-xs text-neutral-500 capitalize">{key.replaceAll("_", " ")}</div>
                <div className="text-xl text-gold-light font-display mt-1">{String(value)}</div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
PYEOF_8
echo "  wrote frontend/src/pages/TodayDashboardPage.tsx"

mkdir -p "$(dirname "frontend/src/components/leads/AddLeadForm.tsx")"
cat > "frontend/src/components/leads/AddLeadForm.tsx" << 'PYEOF_9'
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Branch, SettingsItem } from "@/types";

const VISIT_REASONS = [
  { value: "NEW_PATCH", label: "New Patch" },
  { value: "SERVICE", label: "Service / Maintenance" },
];

export function AddLeadForm({
  branches, sources, statuses, defaultBranchId, onDone,
}: {
  branches: Branch[];
  sources: SettingsItem[];
  statuses: SettingsItem[];
  defaultBranchId?: string | null;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    branch_id: defaultBranchId ?? branches[0]?.id ?? "",
    name: "",
    phone: "",
    email: "",
    lead_source_id: sources[0]?.id ?? "",
    lead_status_id: statuses[0]?.id ?? "",
    visit_reason: "NEW_PATCH",
    notes: "",
    follow_up_date: "",
    follow_up_notes: "",
  });
  const [error, setError] = useState<string | null>(null);

  const createLead = useMutation({
    mutationFn: async () => {
      const { follow_up_date, follow_up_notes, ...leadBody } = form;
      const { data: lead } = await api.post("/leads", leadBody);
      if (follow_up_date) {
        await api.post("/follow-ups", {
          lead_id: lead.id,
          branch_id: form.branch_id,
          due_date: new Date(follow_up_date).toISOString(),
          notes: follow_up_notes || null,
        });
      }
      return lead;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["follow-ups"] });
      onDone();
    },
    onError: (err: any) => setError(err?.response?.data?.detail ?? "Could not create lead"),
  });

  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        createLead.mutate();
      }}
      className="space-y-3"
    >
      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Branch</label>
        <select className="input-field w-full" value={form.branch_id} onChange={(e) => set("branch_id", e.target.value)} required>
          {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Name</label>
          <input className="input-field w-full" value={form.name} onChange={(e) => set("name", e.target.value)} required />
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Phone</label>
          <input className="input-field w-full" value={form.phone} onChange={(e) => set("phone", e.target.value)} placeholder="+91XXXXXXXXXX" required />
        </div>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Email (optional)</label>
        <input type="email" className="input-field w-full" value={form.email} onChange={(e) => set("email", e.target.value)} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Lead Source</label>
          <select className="input-field w-full" value={form.lead_source_id} onChange={(e) => set("lead_source_id", e.target.value)} required>
            {sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-neutral-400 mb-1 block">Status</label>
          <select className="input-field w-full" value={form.lead_status_id} onChange={(e) => set("lead_status_id", e.target.value)} required>
            {statuses.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Visit Reason</label>
        <select className="input-field w-full" value={form.visit_reason} onChange={(e) => set("visit_reason", e.target.value)}>
          {VISIT_REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
      </div>

      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Notes (optional)</label>
        <textarea className="input-field w-full" rows={2} value={form.notes} onChange={(e) => set("notes", e.target.value)} />
      </div>

      <div className="border-t border-charcoal-border pt-3">
        <label className="text-xs text-neutral-400 mb-1 block">Schedule a follow-up (optional)</label>
        <input
          type="date" className="input-field w-full mb-2"
          value={form.follow_up_date} onChange={(e) => set("follow_up_date", e.target.value)}
        />
        {form.follow_up_date && (
          <textarea
            className="input-field w-full" rows={2} placeholder="What to follow up about…"
            value={form.follow_up_notes} onChange={(e) => set("follow_up_notes", e.target.value)}
          />
        )}
      </div>

      {error && <div className="text-sm text-red-400 bg-red-950/30 border border-red-900/50 rounded-lg px-3 py-2">{error}</div>}

      <button type="submit" disabled={createLead.isPending} className="btn-gold w-full disabled:opacity-60">
        {createLead.isPending ? "Adding…" : "Add Lead"}
      </button>
    </form>
  );
}
PYEOF_9
echo "  wrote frontend/src/components/leads/AddLeadForm.tsx"

mkdir -p "$(dirname "frontend/src/components/leads/CompleteFollowUpForm.tsx")"
cat > "frontend/src/components/leads/CompleteFollowUpForm.tsx" << 'PYEOF_10'
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function CompleteFollowUpForm({ followUpId, onDone }: { followUpId: string; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [comment, setComment] = useState("");
  const [scheduleNext, setScheduleNext] = useState(false);
  const [nextDate, setNextDate] = useState("");
  const [nextNotes, setNextNotes] = useState("");

  const complete = useMutation({
    mutationFn: async () =>
      api.post(`/follow-ups/${followUpId}/complete`, {
        comment: comment || null,
        reschedule_due_date: scheduleNext && nextDate ? new Date(nextDate).toISOString() : null,
        reschedule_notes: scheduleNext ? nextNotes || null : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follow-ups"] });
      onDone();
    },
  });

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); complete.mutate(); }}
      className="space-y-4"
    >
      <div>
        <label className="text-xs text-neutral-400 mb-1 block">Comment (optional)</label>
        <textarea
          className="input-field w-full" rows={2} placeholder="How did it go?"
          value={comment} onChange={(e) => setComment(e.target.value)}
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-neutral-300">
        <input type="checkbox" checked={scheduleNext} onChange={(e) => setScheduleNext(e.target.checked)} />
        Schedule next follow-up
      </label>

      {scheduleNext && (
        <div className="space-y-2 pl-1">
          <input
            type="date" className="input-field w-full"
            value={nextDate} onChange={(e) => setNextDate(e.target.value)} required={scheduleNext}
          />
          <textarea
            className="input-field w-full" rows={2} placeholder="Notes for the next follow-up…"
            value={nextNotes} onChange={(e) => setNextNotes(e.target.value)}
          />
        </div>
      )}

      <button type="submit" disabled={complete.isPending} className="btn-gold w-full disabled:opacity-60">
        {complete.isPending ? "Saving…" : "Mark Done"}
      </button>
    </form>
  );
}
PYEOF_10
echo "  wrote frontend/src/components/leads/CompleteFollowUpForm.tsx"

mkdir -p "$(dirname "frontend/src/pages/CallsFollowUpsPage.tsx")"
cat > "frontend/src/pages/CallsFollowUpsPage.tsx" << 'PYEOF_11'
import { useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Modal } from "@/components/shared/Modal";
import { CompleteFollowUpForm } from "@/components/leads/CompleteFollowUpForm";
import { CheckCircle, MessageSquarePlus, Phone } from "lucide-react";
import type { Lead } from "@/types";

interface Comment { text: string; created_at: string; user_name?: string; }
interface FollowUp {
  id: string;
  due_date: string;
  notes?: string | null;
  lead_id?: string | null;
  status: string;
  comments: Comment[];
}

const buckets = ["overdue", "today", "upcoming"] as const;

export default function CallsFollowUpsPage() {
  const [bucket, setBucket] = useState<(typeof buckets)[number]>("today");
  const [completingId, setCompletingId] = useState<string | null>(null);
  const [commentingId, setCommentingId] = useState<string | null>(null);
  const [commentText, setCommentText] = useState("");
  const queryClient = useQueryClient();

  const { data: followUps, isLoading } = useQuery({
    queryKey: ["follow-ups", bucket],
    queryFn: async () => (await api.get<FollowUp[]>("/follow-ups", { params: { bucket } })).data,
  });

  const { data: leads } = useQuery({
    queryKey: ["leads", "all-for-followups"],
    queryFn: async () => (await api.get<Lead[]>("/leads")).data,
  });

  const leadById = useMemo(() => Object.fromEntries((leads ?? []).map((l) => [l.id, l])), [leads]);

  const addComment = useMutation({
    mutationFn: async ({ id, text }: { id: string; text: string }) =>
      api.post(`/follow-ups/${id}/comments`, { text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follow-ups"] });
      setCommentingId(null);
      setCommentText("");
    },
  });

  const bucketCounts: Record<string, number> = {};

  return (
    <div>
      <div className="flex gap-2 mb-6">
        {buckets.map((b) => (
          <button
            key={b}
            onClick={() => setBucket(b)}
            className={`px-4 py-1.5 rounded-full text-sm capitalize transition ${
              bucket === b ? "bg-gold-gradient text-charcoal-950 font-medium" : "border border-charcoal-border text-neutral-400"
            }`}
          >
            {b} {b === "overdue" && "⚠️"}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {isLoading && <div className="text-neutral-600">Loading…</div>}
        {(followUps ?? []).map((fu) => {
          const lead = fu.lead_id ? leadById[fu.lead_id] : null;
          return (
            <div key={fu.id} className="card p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  {lead && (
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-neutral-100">{lead.name}</span>
                      <span className="flex items-center gap-1 text-xs text-neutral-500">
                        <Phone size={11} /> {lead.phone}
                      </span>
                    </div>
                  )}
                  <div className="text-sm text-neutral-300">{fu.notes ?? "Follow-up"}</div>
                  <div className="text-xs text-neutral-500 mt-1">
                    Due {new Date(fu.due_date).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                  </div>

                  {fu.comments.length > 0 && (
                    <div className="mt-3 space-y-1.5 border-l-2 border-charcoal-border pl-3">
                      {fu.comments.map((c, i) => (
                        <div key={i} className="text-xs">
                          <span className="text-neutral-400">{c.text}</span>
                          {c.user_name && <span className="text-neutral-600"> — {c.user_name}</span>}
                        </div>
                      ))}
                    </div>
                  )}

                  {commentingId === fu.id && (
                    <div className="mt-3 flex gap-2">
                      <input
                        className="input-field flex-1 text-sm" placeholder="Add a comment…"
                        value={commentText} onChange={(e) => setCommentText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && commentText.trim()) {
                            addComment.mutate({ id: fu.id, text: commentText.trim() });
                          }
                        }}
                        autoFocus
                      />
                      <button
                        onClick={() => commentText.trim() && addComment.mutate({ id: fu.id, text: commentText.trim() })}
                        className="btn-ghost text-xs px-3"
                      >
                        Post
                      </button>
                    </div>
                  )}
                </div>

                <div className="flex flex-col items-end gap-2 shrink-0">
                  <button
                    onClick={() => setCompletingId(fu.id)}
                    className="text-emerald-400 hover:text-emerald-300 transition flex items-center gap-1 text-sm"
                  >
                    <CheckCircle size={16} /> Done
                  </button>
                  <button
                    onClick={() => setCommentingId(commentingId === fu.id ? null : fu.id)}
                    className="text-neutral-500 hover:text-gold-light transition flex items-center gap-1 text-xs"
                  >
                    <MessageSquarePlus size={14} /> Comment
                  </button>
                </div>
              </div>
            </div>
          );
        })}
        {!isLoading && (followUps ?? []).length === 0 && (
          <div className="text-neutral-600 text-sm">No follow-ups in this bucket.</div>
        )}
      </div>

      <Modal open={!!completingId} onClose={() => setCompletingId(null)} title="Complete Follow-Up">
        {completingId && <CompleteFollowUpForm followUpId={completingId} onDone={() => setCompletingId(null)} />}
      </Modal>
    </div>
  );
}
PYEOF_11
echo "  wrote frontend/src/pages/CallsFollowUpsPage.tsx"

echo "All files applied."

