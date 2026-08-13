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
                           lead_id: str | None = None, _: User = Depends(get_current_user)):
    """bucket: today | overdue | upcoming. When lead_id is given, returns full
    history for that lead (all statuses) rather than only PENDING ones."""
    query = FollowUp.find() if lead_id else FollowUp.find(FollowUp.status == FollowUpStatus.PENDING)
    if branch_id:
        query = query.find(FollowUp.branch_id == branch_id)
    if lead_id:
        query = query.find(FollowUp.lead_id == lead_id)
    items = await query.sort("-due_date" if lead_id else "+due_date").to_list()

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
