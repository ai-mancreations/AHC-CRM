from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User, Branch, Cabin
from app.core.deps import get_current_user, require_super_admin
from app.services.audit import write_audit

router = APIRouter(prefix="/api/branches", tags=["branches"])


class BranchIn(BaseModel):
    name: str
    code: str
    address: str
    city: str
    state: str
    state_code: str
    gstin: str
    phone: str | None = None


class CabinIn(BaseModel):
    branch_id: str
    name: str
    slot_duration_minutes: int = 90


@router.get("")
async def list_branches(_: User = Depends(get_current_user)):
    return await Branch.find(Branch.is_active == True).to_list()  # noqa: E712


@router.post("")
async def create_branch(body: BranchIn, user: User = Depends(require_super_admin)):
    branch = Branch(**body.model_dump())
    await branch.insert()
    await write_audit(user, "CREATE", "branches", str(branch.id), after=branch)
    return branch


@router.put("/{branch_id}")
async def update_branch(branch_id: str, body: BranchIn, user: User = Depends(require_super_admin)):
    branch = await Branch.get(branch_id)
    if not branch:
        raise HTTPException(404, "Branch not found")
    before = branch.model_copy()
    for k, v in body.model_dump().items():
        setattr(branch, k, v)
    branch.updated_at = datetime.now(timezone.utc)
    await branch.save()
    await write_audit(user, "UPDATE", "branches", str(branch.id), before=before, after=branch)
    return branch


@router.get("/cabins")
async def list_cabins(branch_id: str | None = None, _: User = Depends(get_current_user)):
    query = Cabin.find(Cabin.is_archived == False)  # noqa: E712
    if branch_id:
        query = query.find(Cabin.branch_id == branch_id)
    return await query.to_list()


@router.post("/cabins")
async def create_cabin(body: CabinIn, user: User = Depends(require_super_admin)):
    cabin = Cabin(**body.model_dump())
    await cabin.insert()
    await write_audit(user, "CREATE", "cabins", str(cabin.id), after=cabin)
    return cabin
