from datetime import datetime, timedelta
from app.jobs.celery_app import celery_app
from app.jobs.async_helper import run_async


async def _sync_platform(platform: str):
    """Stub sync: real implementation would call the Google Ads / Meta Ads
    reporting API using credentials decrypted from Settings > Integrations
    (see app.core.security.decrypt_secret), then upsert AdCampaign docs.
    This stub just marks existing campaigns for the platform as synced so
    the UI flow can be exercised end-to-end without live credentials."""
    from app.models.misc import AdCampaign
    campaigns = await AdCampaign.find(AdCampaign.platform == platform).to_list()
    for c in campaigns:
        c.last_synced_at = datetime.utcnow()
        await c.save()
    return {"platform": platform, "synced_count": len(campaigns)}


@celery_app.task(name="app.jobs.tasks_ads.sync_ad_platform")
def sync_ad_platform(platform: str):
    return run_async(lambda: _sync_platform(platform))
