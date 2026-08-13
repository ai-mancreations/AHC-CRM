from fastapi import APIRouter, Depends, HTTPException

from app.models.core import User
from app.models.misc import Notification
from app.core.deps import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(unread_only: bool = False, user: User = Depends(get_current_user)):
    query = Notification.find({"$or": [{"user_id": str(user.id)}, {"user_id": None}]})
    items = await query.sort("-created_at").limit(100).to_list()
    if unread_only:
        items = [n for n in items if not n.is_read]
    return items


@router.get("/unread-count")
async def unread_count(user: User = Depends(get_current_user)):
    count = await Notification.find(
        {"$or": [{"user_id": str(user.id)}, {"user_id": None}], "is_read": False}
    ).count()
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, _: User = Depends(get_current_user)):
    n = await Notification.get(notification_id)
    if not n:
        raise HTTPException(404, "Notification not found")
    n.is_read = True
    await n.save()
    return n


@router.post("/mark-all-read")
async def mark_all_read(user: User = Depends(get_current_user)):
    items = await Notification.find(
        {"$or": [{"user_id": str(user.id)}, {"user_id": None}], "is_read": False}
    ).to_list()
    for n in items:
        n.is_read = True
        await n.save()
    return {"updated": len(items)}
