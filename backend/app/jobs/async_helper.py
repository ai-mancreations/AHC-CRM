import asyncio
from app.core.db import init_db


def run_async(coro_factory):
    """Runs an async DB-touching coroutine from within a synchronous Celery task.
    coro_factory is a zero-arg callable returning the coroutine, so init_db()
    can run first in the same event loop."""
    async def _runner():
        await init_db()
        return await coro_factory()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_runner())
    finally:
        loop.close()
