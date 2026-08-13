"""
AI Assistant query service.

Design goal: NEVER execute arbitrary code or arbitrary user-supplied
aggregation pipelines. Instead, this module exposes a small, whitelisted
set of "query intents" (parameterized aggregation templates). The LLM's
job is only to pick an intent + parameters from the whitelist below; it
never generates raw Mongo syntax that gets executed directly.

This file provides:
  - QUERY_INTENTS: the whitelist of allowed report shapes
  - run_intent(): executes a whitelisted intent safely
  - classify_intent(): a lightweight keyword-based classifier used as a
    stand-in for an LLM call so the feature works out of the box without
    external API credentials. Swap in a real Claude API call here later
    (see services/ai_query.py::classify_intent docstring).
"""
from datetime import datetime, timedelta
from typing import Any
from app.core.db import get_client
from app.core.config import get_settings

settings = get_settings()

QUERY_INTENTS = {
    "revenue_by_month": "Total revenue grouped by month for the trailing N months",
    "revenue_by_branch": "Total revenue grouped by branch",
    "leads_by_source": "Lead count grouped by lead source, optionally filtered by status",
    "leads_by_status": "Lead count grouped by pipeline status",
    "top_technicians_by_services": "Technicians ranked by number of services performed",
    "low_stock_items": "Inventory items at or below reorder level",
    "overdue_follow_ups": "Follow-ups past their due date and still pending",
}


async def _db():
    client = get_client()
    return client[settings.MONGO_DB_NAME]


def classify_intent(question: str) -> tuple[str, dict[str, Any]]:
    """
    Lightweight keyword classifier standing in for an LLM call.
    Returns (intent_key, params). Raises ValueError if no whitelisted
    intent matches — the caller must then tell the user the question
    isn't supported yet, never fall back to running raw user input.

    To upgrade this to a real LLM: call the Claude API with a system
    prompt listing QUERY_INTENTS and ask it to respond with strict JSON
    {"intent": "<key>", "params": {...}}, then validate "intent" is a
    key in QUERY_INTENTS before calling run_intent(). Never let the
    model's output be used as a pipeline directly.
    """
    q = question.lower()
    if "revenue" in q and "branch" in q:
        return "revenue_by_branch", {}
    if "revenue" in q or "profit" in q or "sales" in q:
        return "revenue_by_month", {"months": 12}
    if "lead" in q and "source" in q:
        return "leads_by_source", {}
    if "lead" in q and "status" in q or "pipeline" in q:
        return "leads_by_status", {}
    if "technician" in q or "staff" in q:
        return "top_technicians_by_services", {}
    if "low stock" in q or "inventory" in q:
        return "low_stock_items", {}
    if "follow" in q and ("overdue" in q or "pending" in q):
        return "overdue_follow_ups", {}
    raise ValueError("This question isn't supported by the AI Assistant yet.")


async def run_intent(intent: str, params: dict[str, Any], branch_id: str | None = None) -> list[dict]:
    if intent not in QUERY_INTENTS:
        raise ValueError(f"Unknown intent: {intent}")

    db = await _db()
    match_stage: dict[str, Any] = {"is_archived": {"$ne": True}}
    if branch_id:
        match_stage["branch_id"] = branch_id

    if intent == "revenue_by_month":
        months = params.get("months", 12)
        since = datetime.utcnow() - timedelta(days=31 * months)
        pipeline = [
            {"$match": {**match_stage, "issued_at": {"$gte": since}}},
            {"$group": {
                "_id": {"y": {"$year": "$issued_at"}, "m": {"$month": "$issued_at"}},
                "revenue": {"$sum": "$grand_total"},
                "invoice_count": {"$sum": 1},
            }},
            {"$sort": {"_id.y": 1, "_id.m": 1}},
        ]
        return await db["invoices"].aggregate(pipeline).to_list(1000)

    if intent == "revenue_by_branch":
        pipeline = [
            {"$match": match_stage},
            {"$group": {"_id": "$branch_id", "revenue": {"$sum": "$grand_total"}}},
            {"$sort": {"revenue": -1}},
        ]
        return await db["invoices"].aggregate(pipeline).to_list(1000)

    if intent == "leads_by_source":
        pipeline = [
            {"$match": match_stage},
            {"$group": {"_id": "$lead_source_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        return await db["leads"].aggregate(pipeline).to_list(1000)

    if intent == "leads_by_status":
        pipeline = [
            {"$match": match_stage},
            {"$group": {"_id": "$lead_status_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        return await db["leads"].aggregate(pipeline).to_list(1000)

    if intent == "top_technicians_by_services":
        pipeline = [
            {"$match": match_stage},
            {"$group": {"_id": "$technician_id", "service_count": {"$sum": 1}}},
            {"$sort": {"service_count": -1}},
            {"$limit": 10},
        ]
        return await db["services"].aggregate(pipeline).to_list(1000)

    if intent == "low_stock_items":
        pipeline = [
            {"$match": {**match_stage, "$expr": {"$lte": ["$stock_qty", "$reorder_level"]}}},
            {"$sort": {"stock_qty": 1}},
        ]
        return await db["inventory_items"].aggregate(pipeline).to_list(1000)

    if intent == "overdue_follow_ups":
        pipeline = [
            {"$match": {**{k: v for k, v in match_stage.items() if k != "is_archived"},
                        "status": "PENDING", "due_date": {"$lt": datetime.utcnow()}}},
            {"$sort": {"due_date": 1}},
        ]
        return await db["follow_ups"].aggregate(pipeline).to_list(1000)

    return []
