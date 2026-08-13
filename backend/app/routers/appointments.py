from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User
from app.models.appointment import Appointment, WalkIn
from app.models.enums import AppointmentStatus, VisitReasonType
from app.core.deps import get_current_user
from app.services.audit import write_audit

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


class AppointmentIn(BaseModel):
    branch_id: str
    cabin_id: str
    lead_id: str | None = None
    customer_id: str | None = None
    technician_id: str | None = None
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    start_time: datetime
    end_time: datetime
    notes: str | None = None


class WalkInIn(BaseModel):
    branch_id: str
    name: str
    phone: str
    visit_reason: VisitReasonType = VisitReasonType.NEW_PATCH
    notes: str | None = None


async def _has_conflict(cabin_id: str, start: datetime, end: datetime, exclude_id: str | None = None) -> bool:
    existing = await Appointment.find(
        Appointment.cabin_id == cabin_id,
        Appointment.is_archived == False,  # noqa: E712
        Appointment.status.nin([AppointmentStatus.CANCELLED]),
    ).to_list()
    for appt in existing:
        if exclude_id and str(appt.id) == exclude_id:
            continue
        if appt.start_time < end and start < appt.end_time:
            return True
    return False


@router.get("")
async def list_appointments(branch_id: str | None = None, cabin_id: str | None = None,
                             date_from: datetime | None = None, date_to: datetime | None = None,
                             _: User = Depends(get_current_user)):
    query = Appointment.find(Appointment.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Appointment.branch_id == branch_id)
    if cabin_id:
        query = query.find(Appointment.cabin_id == cabin_id)
    items = await query.sort("+start_time").to_list()
    if date_from:
        items = [i for i in items if i.start_time >= date_from]
    if date_to:
        items = [i for i in items if i.start_time <= date_to]
    return items


@router.post("")
async def create_appointment(body: AppointmentIn, user: User = Depends(get_current_user)):
    if body.end_time <= body.start_time:
        raise HTTPException(400, "end_time must be after start_time")
    if await _has_conflict(body.cabin_id, body.start_time, body.end_time):
        raise HTTPException(409, "This cabin is already booked for the selected time slot")

    appt = Appointment(**body.model_dump(), created_by_user_id=str(user.id))
    await appt.insert()
    await write_audit(user, "CREATE", "appointments", str(appt.id), after=appt)
    return appt


@router.put("/{appt_id}")
async def update_appointment(appt_id: str, body: AppointmentIn, user: User = Depends(get_current_user)):
    appt = await Appointment.get(appt_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    if body.end_time <= body.start_time:
        raise HTTPException(400, "end_time must be after start_time")
    if await _has_conflict(body.cabin_id, body.start_time, body.end_time, exclude_id=appt_id):
        raise HTTPException(409, "This cabin is already booked for the selected time slot")

    before = appt.model_copy()
    for k, v in body.model_dump().items():
        setattr(appt, k, v)
    appt.updated_at = datetime.now(timezone.utc)
    await appt.save()
    await write_audit(user, "UPDATE", "appointments", appt_id, before=before, after=appt)
    return appt


@router.post("/{appt_id}/status")
async def set_status(appt_id: str, status: AppointmentStatus, user: User = Depends(get_current_user)):
    appt = await Appointment.get(appt_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    appt.status = status
    appt.updated_at = datetime.now(timezone.utc)
    await appt.save()
    return appt


@router.get("/walk-ins")
async def list_walk_ins(branch_id: str | None = None, _: User = Depends(get_current_user)):
    query = WalkIn.find()
    if branch_id:
        query = query.find(WalkIn.branch_id == branch_id)
    return await query.sort("-visited_at").to_list()


@router.post("/walk-ins")
async def create_walk_in(body: WalkInIn, _: User = Depends(get_current_user)):
    walk_in = WalkIn(**body.model_dump())
    await walk_in.insert()
    return walk_in
