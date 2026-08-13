from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from app.models.core import User
from app.core.deps import get_current_user
from app.core.db import get_client
from app.core.config import get_settings

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
settings = get_settings()


async def _db():
    return get_client()[settings.MONGO_DB_NAME]


def _today_bounds():
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


@router.get("/today")
async def today_dashboard(_: User = Depends(get_current_user)):
    db = await _db()
    start, end = _today_bounds()

    revenue_pipeline = [
        {"$match": {"issued_at": {"$gte": start, "$lt": end}, "is_archived": {"$ne": True}}},
        {"$group": {"_id": "$branch_id", "revenue": {"$sum": "$grand_total"}, "invoice_count": {"$sum": 1}}},
    ]
    revenue_by_branch = await db["invoices"].aggregate(revenue_pipeline).to_list(100)

    leads_today = await db["leads"].count_documents({"created_at": {"$gte": start, "$lt": end}})
    walk_ins_today = await db["walk_ins"].count_documents({"visited_at": {"$gte": start, "$lt": end}})
    conversions_today = await db["leads"].count_documents({"converted_at": {"$gte": start, "$lt": end}})

    leads_by_branch = await db["leads"].aggregate([
        {"$match": {"created_at": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": "$branch_id", "count": {"$sum": 1}}},
    ]).to_list(100)
    walkins_by_branch = await db["walk_ins"].aggregate([
        {"$match": {"visited_at": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": "$branch_id", "count": {"$sum": 1}}},
    ]).to_list(100)

    total_revenue = sum(r["revenue"] for r in revenue_by_branch)

    return {
        "date": start.isoformat(),
        "total_revenue_today": round(total_revenue, 2),
        "leads_today": leads_today,
        "walk_ins_today": walk_ins_today,
        "conversions_today": conversions_today,
        "revenue_by_branch": revenue_by_branch,
        "leads_by_branch": leads_by_branch,
        "walkins_by_branch": walkins_by_branch,
    }


@router.get("/daily-operations")
async def daily_operations(_: User = Depends(get_current_user)):
    db = await _db()
    start, end = _today_bounds()
    tomorrow_start = end
    tomorrow_end = end + timedelta(days=1)

    return {
        "todays_leads": await db["leads"].count_documents({"created_at": {"$gte": start, "$lt": end}}),
        "todays_walk_ins": await db["walk_ins"].count_documents({"visited_at": {"$gte": start, "$lt": end}}),
        "todays_conversions": await db["leads"].count_documents({"converted_at": {"$gte": start, "$lt": end}}),
        "todays_follow_ups_completed": await db["follow_ups"].count_documents(
            {"status": "DONE", "completed_at": {"$gte": start, "$lt": end}}),
        "tomorrows_follow_ups": await db["follow_ups"].count_documents(
            {"status": "PENDING", "due_date": {"$gte": tomorrow_start, "$lt": tomorrow_end}}),
        "todays_new_patch_installations": await db["hair_system_installations"].count_documents(
            {"installed_at": {"$gte": start, "$lt": end}}),
        "todays_appointments": await db["appointments"].count_documents(
            {"start_time": {"$gte": start, "$lt": end}}),
    }


@router.get("/technician-activity")
async def technician_activity(date_from: datetime | None = None, date_to: datetime | None = None,
                               _: User = Depends(get_current_user)):
    db = await _db()
    match = {}
    if date_from or date_to:
        match["performed_at"] = {}
        if date_from:
            match["performed_at"]["$gte"] = date_from
        if date_to:
            match["performed_at"]["$lte"] = date_to
    pipeline = [
        {"$match": match} if match else {"$match": {}},
        {"$group": {"_id": "$technician_id", "service_count": {"$sum": 1}}},
        {"$sort": {"service_count": -1}},
    ]
    return await db["services"].aggregate(pipeline).to_list(200)


@router.get("/profit-trend")
async def profit_trend(months: int = Query(12, ge=1, le=36), branch_id: str | None = None,
                        _: User = Depends(get_current_user)):
    """Monthly revenue, expenses, and net profit across the trailing N months."""
    db = await _db()
    since = datetime.now(timezone.utc) - timedelta(days=31 * months)

    inv_match = {"issued_at": {"$gte": since}, "is_archived": {"$ne": True}}
    exp_match = {"incurred_at": {"$gte": since}, "is_archived": {"$ne": True}}
    if branch_id:
        inv_match["branch_id"] = branch_id
        exp_match["branch_id"] = branch_id

    revenue_pipeline = [
        {"$match": inv_match},
        {"$group": {
            "_id": {"y": {"$year": "$issued_at"}, "m": {"$month": "$issued_at"}},
            "revenue": {"$sum": "$grand_total"},
            "gst_collected": {"$sum": {"$add": ["$total_cgst", "$total_sgst", "$total_igst"]}},
            "invoice_count": {"$sum": 1},
        }},
        {"$sort": {"_id.y": 1, "_id.m": 1}},
    ]
    expense_pipeline = [
        {"$match": exp_match},
        {"$group": {
            "_id": {"y": {"$year": "$incurred_at"}, "m": {"$month": "$incurred_at"}},
            "expenses": {"$sum": "$amount"},
        }},
        {"$sort": {"_id.y": 1, "_id.m": 1}},
    ]
    revenue_rows = await db["invoices"].aggregate(revenue_pipeline).to_list(100)
    expense_rows = await db["expenses"].aggregate(expense_pipeline).to_list(100)

    combined: dict[str, dict] = {}
    for r in revenue_rows:
        key = f"{r['_id']['y']}-{r['_id']['m']:02d}"
        combined.setdefault(key, {"period": key, "revenue": 0, "expenses": 0})
        combined[key]["revenue"] = round(r["revenue"], 2)
    for e in expense_rows:
        key = f"{e['_id']['y']}-{e['_id']['m']:02d}"
        combined.setdefault(key, {"period": key, "revenue": 0, "expenses": 0})
        combined[key]["expenses"] = round(e["expenses"], 2)

    result = []
    for key in sorted(combined.keys()):
        row = combined[key]
        net_profit = round(row["revenue"] - row["expenses"], 2)
        margin = round((net_profit / row["revenue"]) * 100, 1) if row["revenue"] else 0
        result.append({**row, "net_profit": net_profit, "margin_pct": margin})

    return result


@router.get("/profit-comparison")
async def profit_comparison(granularity: str = Query("quarter", pattern="^(month|quarter|fy)$"),
                             branch_id: str | None = None, _: User = Depends(get_current_user)):
    """Quarter-over-quarter or FY-over-FY (April-March) revenue/expense/profit comparison."""
    db = await _db()
    inv_match = {"is_archived": {"$ne": True}}
    exp_match = {"is_archived": {"$ne": True}}
    if branch_id:
        inv_match["branch_id"] = branch_id
        exp_match["branch_id"] = branch_id

    def fy_bucket_expr(field):
        # FY starts April: fy_start_year = year if month>=4 else year-1
        return {
            "$cond": [
                {"$gte": [{"$month": f"${field}"}, 4]},
                {"$year": f"${field}"},
                {"$subtract": [{"$year": f"${field}"}, 1]},
            ]
        }

    if granularity == "month":
        group_id = {"y": {"$year": "$issued_at"}, "m": {"$month": "$issued_at"}}
        exp_group_id = {"y": {"$year": "$incurred_at"}, "m": {"$month": "$incurred_at"}}
    elif granularity == "quarter":
        group_id = {"y": {"$year": "$issued_at"}, "q": {"$ceil": {"$divide": [{"$month": "$issued_at"}, 3]}}}
        exp_group_id = {"y": {"$year": "$incurred_at"}, "q": {"$ceil": {"$divide": [{"$month": "$incurred_at"}, 3]}}}
    else:  # fy
        group_id = {"fy": fy_bucket_expr("issued_at")}
        exp_group_id = {"fy": fy_bucket_expr("incurred_at")}

    revenue_rows = await db["invoices"].aggregate([
        {"$match": inv_match},
        {"$group": {"_id": group_id, "revenue": {"$sum": "$grand_total"}}},
        {"$sort": {"_id": 1}},
    ]).to_list(200)
    expense_rows = await db["expenses"].aggregate([
        {"$match": exp_match},
        {"$group": {"_id": exp_group_id, "expenses": {"$sum": "$amount"}}},
        {"$sort": {"_id": 1}},
    ]).to_list(200)

    def label(_id):
        if granularity == "month":
            return f"{_id['y']}-{_id['m']:02d}"
        if granularity == "quarter":
            return f"{_id['y']}-Q{int(_id['q'])}"
        return f"FY{str(_id['fy'])[-2:]}-{str(_id['fy']+1)[-2:]}"

    combined: dict[str, dict] = {}
    for r in revenue_rows:
        key = label(r["_id"])
        combined.setdefault(key, {"period": key, "revenue": 0, "expenses": 0})
        combined[key]["revenue"] = round(r["revenue"], 2)
    for e in expense_rows:
        key = label(e["_id"])
        combined.setdefault(key, {"period": key, "revenue": 0, "expenses": 0})
        combined[key]["expenses"] = round(e["expenses"], 2)

    result = []
    for key in sorted(combined.keys()):
        row = combined[key]
        row["net_profit"] = round(row["revenue"] - row["expenses"], 2)
        result.append(row)
    return result


@router.get("/revenue-breakdown")
async def revenue_breakdown(by: str = Query(..., pattern="^(service_type|technician|branch|source)$"),
                             date_from: datetime | None = None, date_to: datetime | None = None,
                             _: User = Depends(get_current_user)):
    db = await _db()
    date_match = {}
    if date_from or date_to:
        date_match["issued_at"] = {}
        if date_from:
            date_match["issued_at"]["$gte"] = date_from
        if date_to:
            date_match["issued_at"]["$lte"] = date_to

    if by == "branch":
        pipeline = [{"$match": {**date_match, "is_archived": {"$ne": True}}},
                    {"$group": {"_id": "$branch_id", "revenue": {"$sum": "$grand_total"}}}]
        return await db["invoices"].aggregate(pipeline).to_list(100)

    if by == "service_type":
        pipeline = [
            {"$match": {**date_match, "is_archived": {"$ne": True}}},
            {"$unwind": "$lines"},
            {"$group": {"_id": "$lines.service_type_id", "revenue": {"$sum": "$lines.line_total"}}},
        ]
        return await db["invoices"].aggregate(pipeline).to_list(200)

    if by == "technician":
        pipeline = [
            {"$match": {} if not date_match else {"performed_at": date_match.get("issued_at", {})}},
            {"$group": {"_id": "$technician_id", "revenue": {"$sum": "$price_charged"}}},
        ]
        return await db["services"].aggregate(pipeline).to_list(200)

    if by == "source":
        # revenue for customers whose originating lead had a given source
        pipeline = [
            {"$match": {**date_match, "is_archived": {"$ne": True}}},
            {"$lookup": {"from": "customers", "localField": "customer_id", "foreignField": "_id",
                         "as": "customer"}},
        ]
        # Fallback: leads store lead_source_id; join through customer.source_lead_id -> lead
        invoices = await db["invoices"].aggregate([{"$match": {**date_match, "is_archived": {"$ne": True}}}]).to_list(2000)
        customers = {str(c["_id"]): c async for c in db["customers"].find({})}
        leads = {str(l["_id"]): l async for l in db["leads"].find({})}
        totals: dict[str, float] = {}
        for inv in invoices:
            cust = customers.get(inv["customer_id"])
            source_id = "UNKNOWN"
            if cust and cust.get("source_lead_id"):
                lead = leads.get(cust["source_lead_id"])
                if lead:
                    source_id = lead.get("lead_source_id", "UNKNOWN")
            totals[source_id] = totals.get(source_id, 0) + inv.get("grand_total", 0)
        return [{"_id": k, "revenue": round(v, 2)} for k, v in totals.items()]


@router.get("/drill-down")
async def drill_down(period: str, granularity: str = Query("month", pattern="^(month|quarter|fy)$"),
                      branch_id: str | None = None, _: User = Depends(get_current_user)):
    """Given a period label (e.g. '2026-03', '2026-Q1', 'FY25-26'), return the underlying invoices."""
    db = await _db()
    match = {"is_archived": {"$ne": True}}
    if branch_id:
        match["branch_id"] = branch_id

    invoices = await db["invoices"].aggregate([{"$match": match}]).to_list(5000)
    filtered = []
    for inv in invoices:
        dt = inv["issued_at"]
        if granularity == "month":
            key = f"{dt.year}-{dt.month:02d}"
        elif granularity == "quarter":
            key = f"{dt.year}-Q{(dt.month - 1)//3 + 1}"
        else:
            fy_start = dt.year if dt.month >= 4 else dt.year - 1
            key = f"FY{str(fy_start)[-2:]}-{str(fy_start+1)[-2:]}"
        if key == period:
            filtered.append(inv)
    return filtered
