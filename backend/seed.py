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
