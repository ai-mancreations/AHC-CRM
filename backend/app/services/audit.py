from typing import Optional, Any
from beanie import Document

from app.models.misc import AuditLog
from app.models.core import User


def _serialize(doc: Optional[Document | dict]) -> Optional[dict]:
    if doc is None:
        return None
    if isinstance(doc, dict):
        return doc
    data = doc.model_dump(mode="json")
    data.pop("_id", None)
    return data


async def write_audit(
    user: User,
    action: str,
    collection_name: str,
    document_id: str,
    before: Optional[Document | dict] = None,
    after: Optional[Document | dict] = None,
) -> None:
    entry = AuditLog(
        user_id=str(user.id),
        user_email=user.email,
        action=action,
        collection_name=collection_name,
        document_id=str(document_id),
        before=_serialize(before),
        after=_serialize(after),
    )
    await entry.insert()
