import logging

from sqlalchemy import delete, or_

from app.auth.models import AuthSession
from app.database import AsyncSessionLocal, utc_now


logger = logging.getLogger(__name__)


async def cleanup_old_sessions() -> int:
    """Удаляет истёкшие и отозванные сессии одним SQL-запросом."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(AuthSession).where(
                or_(
                    AuthSession.expires_at <= utc_now(),
                    AuthSession.revoked_at.is_not(None),
                )
            )
        )
        await db.commit()

    deleted_count = result.rowcount or 0
    logger.info("Очистка сессий: удалено %s записей", deleted_count)
    return deleted_count
