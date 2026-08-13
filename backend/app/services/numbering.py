from datetime import datetime
from pymongo import ReturnDocument
from app.core.db import get_client
from app.core.config import get_settings
from app.services.gst import financial_year_short_code, financial_year_label

settings = get_settings()


async def next_invoice_number(branch_code: str, issued_at: datetime | None = None) -> tuple[str, str]:
    """
    Atomically increments a per-branch, per-financial-year counter and returns
    (invoice_number, financial_year_label).
    Format: AHC/{BRANCH}/{FY}/{seq:04d}, e.g. AHC/HYD/2526/0001
    """
    issued_at = issued_at or datetime.utcnow()
    fy_code = financial_year_short_code(issued_at, settings.FY_START_MONTH)
    fy_label = financial_year_label(issued_at, settings.FY_START_MONTH)
    key = f"INV-{branch_code}-FY{fy_code}"

    client = get_client()
    db = client[settings.MONGO_DB_NAME]
    result = await db["counters"].find_one_and_update(
        {"key": key},
        {"$inc": {"value": 1}, "$setOnInsert": {"key": key}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    seq = result["value"]
    invoice_number = f"AHC/{branch_code}/{fy_code}/{seq:04d}"
    return invoice_number, fy_label
