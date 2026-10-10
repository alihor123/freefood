import logging
from datetime import datetime, timezone

from app.database.database import AsyncSessionLocal
from app.database.repositories.session_repo import cleanup_sessions


logger = logging.getLogger(__name__)


async def cleanup_old_sessions() -> int:
    """Удаляет все истёкшие и отозванные сессии одним SQL-запросом."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        deleted_count = await cleanup_sessions(db, now)
    logger.info("Очистка сессий: удалено %s записей", deleted_count)
    return deleted_count
