import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.models.core import User
from app.models.invoice import Invoice
from app.models.misc import Expense
from app.models.inventory import InventoryItem
from app.models.lead import Lead
from app.core.deps import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/sales.csv")
async def sales_report(branch_id: str | None = None, date_from: datetime | None = None,
                        date_to: datetime | None = None, _: User = Depends(get_current_user)):
    query = Invoice.find(Invoice.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Invoice.branch_id == branch_id)
    items = await query.to_list()
    if date_from:
        items = [i for i in items if i.issued_at >= date_from]
    if date_to:
        items = [i for i in items if i.issued_at <= date_to]
    rows = [{"invoice_number": i.invoice_number, "branch_id": i.branch_id, "customer_id": i.customer_id,
             "issued_at": i.issued_at.isoformat(), "subtotal": i.subtotal, "grand_total": i.grand_total,
             "status": i.status.value} for i in items]
    return _csv_response(rows, "sales_report.csv")


@router.get("/financial.csv")
async def financial_report(branch_id: str | None = None, date_from: datetime | None = None,
                            date_to: datetime | None = None, _: User = Depends(get_current_user)):
    inv_query = Invoice.find(Invoice.is_archived == False)  # noqa: E712
    exp_query = Expense.find(Expense.is_archived == False)  # noqa: E712
    if branch_id:
        inv_query = inv_query.find(Invoice.branch_id == branch_id)
        exp_query = exp_query.find(Expense.branch_id == branch_id)
    invoices = await inv_query.to_list()
    expenses = await exp_query.to_list()

    rows = []
    for i in invoices:
        if date_from and i.issued_at < date_from:
            continue
        if date_to and i.issued_at > date_to:
            continue
        rows.append({"type": "REVENUE", "date": i.issued_at.isoformat(), "branch_id": i.branch_id,
                      "amount": i.grand_total, "reference": i.invoice_number})
    for e in expenses:
        if date_from and e.incurred_at < date_from:
            continue
        if date_to and e.incurred_at > date_to:
            continue
        rows.append({"type": "EXPENSE", "date": e.incurred_at.isoformat(), "branch_id": e.branch_id,
                      "amount": -e.amount, "reference": e.description})
    rows.sort(key=lambda r: r["date"])
    return _csv_response(rows, "financial_report.csv")


@router.get("/inventory.csv")
async def inventory_report(branch_id: str | None = None, _: User = Depends(get_current_user)):
    query = InventoryItem.find(InventoryItem.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(InventoryItem.branch_id == branch_id)
    items = await query.to_list()
    rows = [{"name": i.name, "branch_id": i.branch_id, "stock_qty": i.stock_qty,
             "reorder_level": i.reorder_level, "unit_cost": i.unit_cost,
             "low_stock": i.is_low_stock,
             "expiry_date": i.expiry_date.isoformat() if i.expiry_date else ""} for i in items]
    return _csv_response(rows, "inventory_report.csv")


@router.get("/lead-pipeline.csv")
async def lead_pipeline_report(branch_id: str | None = None, _: User = Depends(get_current_user)):
    query = Lead.find(Lead.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Lead.branch_id == branch_id)
    items = await query.to_list()
    rows = [{"name": i.name, "phone": i.phone, "branch_id": i.branch_id,
             "lead_source_id": i.lead_source_id, "lead_status_id": i.lead_status_id,
             "created_at": i.created_at.isoformat(),
             "converted": bool(i.converted_customer_id)} for i in items]
    return _csv_response(rows, "lead_pipeline_report.csv")
