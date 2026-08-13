from enum import Enum


class Role(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    MANAGER = "MANAGER"


class VisitReasonType(str, Enum):
    NEW_PATCH = "NEW_PATCH"
    SERVICE = "SERVICE"


class AppointmentStatus(str, Enum):
    BOOKED = "BOOKED"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"
    CANCELLED = "CANCELLED"


class CallOutcome(str, Enum):
    CONNECTED = "CONNECTED"
    NO_ANSWER = "NO_ANSWER"
    BUSY = "BUSY"
    WRONG_NUMBER = "WRONG_NUMBER"
    CALL_BACK_LATER = "CALL_BACK_LATER"
    NOT_INTERESTED = "NOT_INTERESTED"
    INTERESTED = "INTERESTED"


class FollowUpStatus(str, Enum):
    PENDING = "PENDING"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class GstType(str, Enum):
    INTRA_STATE = "INTRA_STATE"  # CGST + SGST
    INTER_STATE = "INTER_STATE"  # IGST


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    PAID = "PAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, Enum):
    CASH = "CASH"
    UPI = "UPI"
    CARD = "CARD"
    NEFT = "NEFT"
    CHEQUE = "CHEQUE"


class PurchaseOrderStatus(str, Enum):
    DRAFT = "DRAFT"
    ORDERED = "ORDERED"
    RECEIVED = "RECEIVED"
    CLOSED = "CLOSED"


class InventoryTxnType(str, Enum):
    RECEIPT = "RECEIPT"
    DEDUCTION = "DEDUCTION"
    ADJUSTMENT = "ADJUSTMENT"
    TRANSFER = "TRANSFER"


class ImportStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    ROLLED_BACK = "ROLLED_BACK"


class NotificationType(str, Enum):
    NEW_LEAD = "NEW_LEAD"
    OVERDUE_FOLLOW_UP = "OVERDUE_FOLLOW_UP"
    LOW_STOCK = "LOW_STOCK"
    UPCOMING_APPOINTMENT = "UPCOMING_APPOINTMENT"
    EXPIRING_INVENTORY = "EXPIRING_INVENTORY"
    OTHER = "OTHER"
