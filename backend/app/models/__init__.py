from app.models.core import User, Branch, Cabin
from app.models.settings_entity import SettingsItem, ServiceType, MessageTemplate
from app.models.config import CompanyConfig, Integration, Counter
from app.models.lead import Lead, LeadActivity, Call, FollowUp
from app.models.appointment import Appointment, WalkIn, Customer, Technician
from app.models.service import Service, HairSystemInstallation
from app.models.inventory import InventoryItem, InventoryTransaction, PurchaseOrder
from app.models.invoice import Invoice, Payment
from app.models.misc import Expense, AdCampaign, Notification, AuditLog, ImportBatch

ALL_DOCUMENT_MODELS = [
    User,
    Branch,
    Cabin,
    SettingsItem,
    ServiceType,
    MessageTemplate,
    CompanyConfig,
    Integration,
    Counter,
    Lead,
    LeadActivity,
    Call,
    FollowUp,
    Appointment,
    WalkIn,
    Customer,
    Technician,
    Service,
    HairSystemInstallation,
    InventoryItem,
    InventoryTransaction,
    PurchaseOrder,
    Invoice,
    Payment,
    Expense,
    AdCampaign,
    Notification,
    AuditLog,
    ImportBatch,
]
