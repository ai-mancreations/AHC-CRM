from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User
from app.models.misc import Expense
from app.core.deps import get_current_user, require_super_admin
from app.services.audit import write_audit

router = APIRouter(prefix="/api/expenses", tags=["expenses"])


class ExpenseIn(BaseModel):
    branch_id: str
    category_id: str
    description: str
    amount: float
    receipt_url: str | None = None
    is_recurring: bool = False
    incurred_at: datetime


@router.get("")
async def list_expenses(branch_id: str | None = None, category_id: str | None = None,
                         date_from: datetime | None = None, date_to: datetime | None = None,
                         _: User = Depends(get_current_user)):
    query = Expense.find(Expense.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Expense.branch_id == branch_id)
    if category_id:
        query = query.find(Expense.category_id == category_id)
    items = await query.sort("-incurred_at").to_list()
    if date_from:
        items = [i for i in items if i.incurred_at >= date_from]
    if date_to:
        items = [i for i in items if i.incurred_at <= date_to]
    return items


@router.post("")
async def create_expense(body: ExpenseIn, user: User = Depends(get_current_user)):
    expense = Expense(**body.model_dump(), recorded_by_user_id=str(user.id))
    await expense.insert()
    await write_audit(user, "CREATE", "expenses", str(expense.id), after=expense)
    return expense


@router.post("/{expense_id}/archive")
async def archive_expense(expense_id: str, user: User = Depends(require_super_admin)):
    expense = await Expense.get(expense_id)
    if not expense:
        raise HTTPException(404, "Expense not found")
    expense.is_archived = True
    await expense.save()
    await write_audit(user, "ARCHIVE", "expenses", expense_id, after=expense)
    return expense
