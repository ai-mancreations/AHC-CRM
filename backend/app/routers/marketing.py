from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.models.core import User
from app.models.misc import AdCampaign
from app.core.deps import get_current_user, require_super_admin

router = APIRouter(prefix="/api/marketing", tags=["marketing"])


class AdCampaignIn(BaseModel):
    branch_id: str | None = None
    platform: str
    campaign_name: str
    external_campaign_id: str | None = None
    spend: float = 0
    impressions: int = 0
    clicks: int = 0
    leads_generated: int = 0
    conversions: int = 0
    period_start: datetime
    period_end: datetime


@router.get("/campaigns")
async def list_campaigns(platform: str | None = None, branch_id: str | None = None,
                          _: User = Depends(get_current_user)):
    query = AdCampaign.find()
    if platform:
        query = query.find(AdCampaign.platform == platform)
    if branch_id:
        query = query.find(AdCampaign.branch_id == branch_id)
    items = await query.sort("-period_start").to_list()
    return [
        {**c.model_dump(mode="json"), "id": str(c.id), "cpl": c.cpl, "cac": c.cac,
         "roas": round(c.spend / c.conversions, 2) if c.conversions else 0}
        for c in items
    ]


@router.post("/campaigns")
async def create_campaign(body: AdCampaignIn, _: User = Depends(require_super_admin)):
    campaign = AdCampaign(**body.model_dump())
    await campaign.insert()
    return campaign


@router.post("/sync/{platform}")
async def trigger_sync(platform: str, user: User = Depends(require_super_admin)):
    """Enqueues the Celery ad-sync task for the given platform (GOOGLE_ADS | META_ADS).
    Actual provider API calls are stubbed until real credentials are configured
    in Settings > Integrations (see app/jobs/tasks_ads.py)."""
    try:
        from app.jobs.tasks_ads import sync_ad_platform
        sync_ad_platform.delay(platform)
        return {"queued": True, "platform": platform}
    except Exception as e:
        return {"queued": False, "platform": platform, "error": str(e),
                "note": "Celery broker not reachable in this environment; task not enqueued."}
