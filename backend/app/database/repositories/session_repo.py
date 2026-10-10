from datetime import datetime, timezone

from sqlalchemy import delete, select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AuthSession


async def get_active_session(
    session_id: str,
    user_id: int,
    db: AsyncSession,
) -> AuthSession | None:
    """Находит неотозванную сессию; срок самого JWT уже проверил AuthX."""
    return await db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
    )


async def rotate_refresh_token(
    session_id: str,
    user_id: int,
    old_hash: str,
    new_hash: str,
    new_expires_at: datetime,
    db: AsyncSession,
) -> bool:
    """Заменяет хеш только если предъявлен текущий токен активной сессии."""
    result = await db.execute(
        update(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.refresh_token_hash == old_hash,
            AuthSession.revoked_at.is_(None),
        )
        .values(refresh_token_hash=new_hash, expires_at=new_expires_at)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


async def revoke_session(
    session_id: str,
    user_id: int,
    db: AsyncSession,
) -> bool:
    """Помечает текущую неотозванную сессию временем выхода."""
    result = await db.execute(
        update(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    return result.rowcount == 1


async def cleanup_sessions(db: AsyncSession, now: datetime) -> int:
    """Удаляет сессии с истёкшим сроком refresh и все отозванные сессии."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    result = await db.execute(
        delete(AuthSession).where(
            or_(
                AuthSession.expires_at <= now,
                AuthSession.revoked_at.is_not(None),
            )
        )
    )
    await db.commit()
    return result.rowcount or 0
