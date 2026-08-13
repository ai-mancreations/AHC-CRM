from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.models.core import User
from app.models.misc import AuditLog
from app.models.enums import Role
from app.core.deps import get_current_user, require_super_admin
from app.core.security import hash_password
from app.services.audit import write_audit

audit_router = APIRouter(prefix="/api/audit-log", tags=["audit"])
users_router = APIRouter(prefix="/api/users", tags=["users"])


@audit_router.get("")
async def list_audit_log(user_id: str | None = None, action: str | None = None,
                          collection_name: str | None = None,
                          date_from: datetime | None = None, date_to: datetime | None = None,
                          _: User = Depends(require_super_admin)):
    query = AuditLog.find()
    if user_id:
        query = query.find(AuditLog.user_id == user_id)
    if action:
        query = query.find(AuditLog.action == action)
    if collection_name:
        query = query.find(AuditLog.collection_name == collection_name)
    items = await query.sort("-created_at").limit(500).to_list()
    if date_from:
        items = [i for i in items if i.created_at >= date_from]
    if date_to:
        items = [i for i in items if i.created_at <= date_to]
    return items


class UserIn(BaseModel):
    email: EmailStr
    name: str
    role: Role
    phone: str | None = None
    password: str


class UserUpdateIn(BaseModel):
    name: str | None = None
    role: Role | None = None
    phone: str | None = None
    is_active: bool | None = None


@users_router.get("")
async def list_users(_: User = Depends(require_super_admin)):
    users = await User.find_all().to_list()
    return [{"id": str(u.id), "email": u.email, "name": u.name, "role": u.role,
             "phone": u.phone, "is_active": u.is_active} for u in users]


@users_router.post("")
async def create_user(body: UserIn, admin: User = Depends(require_super_admin)):
    existing = await User.find_one(User.email == body.email)
    if existing:
        raise HTTPException(400, "A user with this email already exists")
    user = User(email=body.email, name=body.name, role=body.role, phone=body.phone,
                password_hash=hash_password(body.password))
    await user.insert()
    await write_audit(admin, "CREATE", "users", str(user.id))
    return {"id": str(user.id), "email": user.email, "name": user.name, "role": user.role}


@users_router.put("/{user_id}")
async def update_user(user_id: str, body: UserUpdateIn, admin: User = Depends(require_super_admin)):
    user = await User.get(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    await user.save()
    await write_audit(admin, "UPDATE", "users", user_id)
    return {"id": str(user.id), "email": user.email, "name": user.name, "role": user.role,
            "is_active": user.is_active}
