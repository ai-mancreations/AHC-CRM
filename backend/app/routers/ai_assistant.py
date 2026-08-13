from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.models.core import User
from app.core.deps import get_current_user
from app.services.ai_query import classify_intent, run_intent, QUERY_INTENTS

router = APIRouter(prefix="/api/ai-assistant", tags=["ai-assistant"])


class AskIn(BaseModel):
    question: str
    branch_id: str | None = None


@router.get("/capabilities")
async def capabilities(_: User = Depends(get_current_user)):
    return QUERY_INTENTS


@router.post("/ask")
async def ask(body: AskIn, _: User = Depends(get_current_user)):
    try:
        intent, params = classify_intent(body.question)
    except ValueError as e:
        return {"answer": str(e), "supported": False, "data": []}

    data = await run_intent(intent, params, branch_id=body.branch_id)
    return {"answer": f"Here's what I found for: {QUERY_INTENTS[intent]}", "supported": True,
            "intent": intent, "data": data}
