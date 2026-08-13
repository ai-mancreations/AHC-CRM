from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import get_settings
from app.models import ALL_DOCUMENT_MODELS

settings = get_settings()

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        # tz_aware=True is critical: without it, Motor/PyMongo returns naive
        # datetimes (no tzinfo) for every date read from Mongo, while the rest
        # of the app works with timezone-aware UTC datetimes (from
        # datetime.now(timezone.utc) and from parsing incoming ISO-8601
        # request bodies). Comparing a naive and an aware datetime raises a
        # TypeError in Python — this was silently breaking appointment
        # double-booking checks, follow-up due-date bucketing, and inventory
        # expiry filtering, whenever there was existing data to compare against.
        _client = AsyncIOMotorClient(settings.MONGO_URI, tz_aware=True)
    return _client


async def init_db():
    client = get_client()
    db = client[settings.MONGO_DB_NAME]
    await init_beanie(database=db, document_models=ALL_DOCUMENT_MODELS)
    return db
