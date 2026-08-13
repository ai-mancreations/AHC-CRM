from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User, Branch
from app.models.appointment import Customer
from app.models.invoice import Invoice, InvoiceLine, Payment
from app.models.enums import InvoiceStatus, PaymentMethod
from app.core.deps import get_current_user
from app.services.gst import determine_gst_type, compute_line_tax
from app.services.numbering import next_invoice_number
from app.services.invoice_pdf import upload_invoice_pdf
from app.services.audit import write_audit

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


class InvoiceLineIn(BaseModel):
    description: str
    hsn_sac_code: str = "999599"
    service_type_id: str | None = None
    inventory_item_id: str | None = None
    qty: float = 1
    unit_price: float
    gst_rate: float = 18.0


class InvoiceIn(BaseModel):
    branch_id: str
    customer_id: str
    lines: list[InvoiceLineIn]
    due_date: datetime | None = None
    notes: str | None = None


class PaymentIn(BaseModel):
    amount: float
    method: PaymentMethod
    reference_no: str | None = None
    notes: str | None = None


@router.get("")
async def list_invoices(branch_id: str | None = None, customer_id: str | None = None,
                         status: InvoiceStatus | None = None,
                         date_from: datetime | None = None, date_to: datetime | None = None,
                         _: User = Depends(get_current_user)):
    query = Invoice.find(Invoice.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Invoice.branch_id == branch_id)
    if customer_id:
        query = query.find(Invoice.customer_id == customer_id)
    if status:
        query = query.find(Invoice.status == status)
    items = await query.sort("-issued_at").to_list()
    if date_from:
        items = [i for i in items if i.issued_at >= date_from]
    if date_to:
        items = [i for i in items if i.issued_at <= date_to]
    return items


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: str, _: User = Depends(get_current_user)):
    invoice = await Invoice.get(invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    payments = await Payment.find(Payment.invoice_id == invoice_id).sort("-paid_at").to_list()
    return {"invoice": invoice, "payments": payments}


@router.post("")
async def create_invoice(body: InvoiceIn, user: User = Depends(get_current_user)):
    branch = await Branch.get(body.branch_id)
    if not branch:
        raise HTTPException(404, "Branch not found")
    customer = await Customer.get(body.customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")

    gst_type = determine_gst_type(branch.state_code, customer.gst_state_code)

    lines: list[InvoiceLine] = []
    subtotal = total_cgst = total_sgst = total_igst = 0.0
    for l in body.lines:
        taxable_value = round(l.qty * l.unit_price, 2)
        tax = compute_line_tax(taxable_value, l.gst_rate, gst_type)
        line_total = round(taxable_value + tax["cgst_amount"] + tax["sgst_amount"] + tax["igst_amount"], 2)
        lines.append(InvoiceLine(
            description=l.description, hsn_sac_code=l.hsn_sac_code, service_type_id=l.service_type_id,
            inventory_item_id=l.inventory_item_id, qty=l.qty, unit_price=l.unit_price,
            taxable_value=taxable_value, gst_rate=l.gst_rate, line_total=line_total, **tax,
        ))
        subtotal += taxable_value
        total_cgst += tax["cgst_amount"]
        total_sgst += tax["sgst_amount"]
        total_igst += tax["igst_amount"]

    grand_total = round(subtotal + total_cgst + total_sgst + total_igst, 2)
    invoice_number, fy_label = await next_invoice_number(branch.code)

    invoice = Invoice(
        branch_id=body.branch_id, customer_id=body.customer_id, invoice_number=invoice_number,
        financial_year=fy_label, gst_type=gst_type, lines=lines, subtotal=round(subtotal, 2),
        total_cgst=round(total_cgst, 2), total_sgst=round(total_sgst, 2), total_igst=round(total_igst, 2),
        grand_total=grand_total, status=InvoiceStatus.DRAFT, due_date=body.due_date, notes=body.notes,
        created_by_user_id=str(user.id),
    )
    await invoice.insert()

    # attempt PDF generation; non-fatal if it fails (e.g. weasyprint system libs unavailable)
    try:
        pdf_url = await upload_invoice_pdf(invoice, branch, customer)
        if pdf_url:
            invoice.pdf_url = pdf_url
            await invoice.save()
    except Exception:
        pass

    await write_audit(user, "CREATE", "invoices", str(invoice.id), after=invoice)
    return invoice


@router.post("/{invoice_id}/payments")
async def record_payment(invoice_id: str, body: PaymentIn, user: User = Depends(get_current_user)):
    invoice = await Invoice.get(invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    payment = Payment(invoice_id=invoice_id, branch_id=invoice.branch_id, amount=body.amount,
                       method=body.method, reference_no=body.reference_no, notes=body.notes,
                       recorded_by_user_id=str(user.id))
    await payment.insert()

    invoice.amount_paid = round(invoice.amount_paid + body.amount, 2)
    if invoice.amount_paid >= invoice.grand_total:
        invoice.status = InvoiceStatus.PAID
    elif invoice.amount_paid > 0:
        invoice.status = InvoiceStatus.PARTIALLY_PAID
    invoice.updated_at = datetime.now(timezone.utc)
    await invoice.save()

    await write_audit(user, "CREATE", "payments", str(payment.id), after=payment)
    return {"invoice": invoice, "payment": payment}


@router.post("/{invoice_id}/mark-overdue")
async def mark_overdue(invoice_id: str, user: User = Depends(get_current_user)):
    invoice = await Invoice.get(invoice_id)
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    invoice.status = InvoiceStatus.OVERDUE
    await invoice.save()
    return invoice
