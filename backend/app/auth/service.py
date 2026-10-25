import hashlib
from datetime import datetime
from uuid import uuid4

from authx import RequestToken, TokenPayload
from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import AuthSession, User
from app.auth.schemas import AccessRefreshDTO, UserDTO
from app.auth.telegram import verify_telegram_init_data
from app.auth.tokens import create_session_token_pair, security
from app.config import settings
from app.database import utc_now


async def get_active_session(
    payload: TokenPayload,
    db: AsyncSession,
) -> tuple[AuthSession, User]:
    """Проверяет сессию из JWT и возвращает её вместе с пользователем."""
    session_id = getattr(payload, "session_id", None)
    if not isinstance(session_id, str):
        raise HTTPException(status_code=401, detail="Некорректные данные токена")

    result = await db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utc_now(),
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(status_code=401, detail="Сессия завершена или не найдена")

    session, user = row
    if str(user.id) != payload.sub:
        raise HTTPException(status_code=401, detail="Некорректные данные токена")
    return session, user


async def login_with_telegram(
    init_data: str,
    device_id: str,
    db: AsyncSession,
) -> AccessRefreshDTO:
    """Создаёт или обновляет сессию устройства после проверки Telegram."""
    identity = verify_telegram_init_data(init_data)
    if identity is None:
        raise HTTPException(status_code=401, detail="Данные Telegram недействительны")

    user = await db.scalar(
        select(User).where(User.telegram_id == identity["telegram_id"])
    )
    if user is None:
        user = User(**identity)
        db.add(user)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            # Другой первый вход мог успеть создать эту запись.
            user = await db.scalar(
                select(User).where(User.telegram_id == identity["telegram_id"])
            )
            if user is None:
                raise

    # UPDATE также упорядочивает одновременные входы одного пользователя.
    await db.execute(update(User).where(User.id == user.id).values(**identity))
    return await create_or_update_session(user, device_id, db)


async def create_or_update_session(
    user: User,
    device_id: str,
    db: AsyncSession,
) -> AccessRefreshDTO:
    """Находит сессию устройства и сохраняет новую пару токенов в пределах лимита."""
    session = await db.scalar(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.device_id == device_id,
        )
    )
    if session is not None and (
        session.revoked_at is not None or session.expires_at <= utc_now()
    ):
        await db.delete(session)
        await db.flush()
        session = None

    if session is None:
        session = AuthSession(
            id=str(uuid4()),
            user_id=user.id,
            device_id=device_id,
        )
        db.add(session)

    tokens, access_expires_at, refresh_expires_at = create_session_token_pair(
        user.id,
        session.id,
    )
    session.refresh_token_hash = hashlib.sha256(
        tokens.refresh_token.encode("utf-8")
    ).hexdigest()
    session.expires_at = refresh_expires_at
    await db.flush()

    # Сохраняем текущую сессию и последние активные в пределах лимита.
    old_sessions = (
        select(AuthSession.id)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.id != session.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utc_now(),
        )
        .order_by(AuthSession.created_at.desc(), AuthSession.id.desc())
        .offset(settings.MAX_ACTIVE_SESSIONS - 1)
    )
    await db.execute(delete(AuthSession).where(AuthSession.id.in_(old_sessions)))
    await db.commit()
    return _build_response(
        user,
        tokens.access_token,
        tokens.refresh_token,
        access_expires_at,
    )


async def refresh_tokens(
    refresh_token: RequestToken,
    db: AsyncSession,
) -> AccessRefreshDTO:
    """Атомарно заменяет refresh-хеш и сохраняет ID сессии."""
    payload = security.verify_token(refresh_token, verify_csrf=False)
    session, user = await get_active_session(payload, db)

    tokens, access_expires_at, refresh_expires_at = create_session_token_pair(
        user.id,
        session.id,
    )
    old_hash = hashlib.sha256(refresh_token.token.encode("utf-8")).hexdigest()
    new_hash = hashlib.sha256(tokens.refresh_token.encode("utf-8")).hexdigest()
    # Условие UPDATE защищает от одновременного refresh и отзыва сессии.
    result = await db.execute(
        update(AuthSession)
        .where(
            AuthSession.id == session.id,
            AuthSession.user_id == user.id,
            AuthSession.refresh_token_hash == old_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utc_now(),
        )
        .values(
            refresh_token_hash=new_hash,
            expires_at=refresh_expires_at,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(
            status_code=401,
            detail="Refresh-токен уже использован или сессия завершена",
        )

    await db.commit()
    return _build_response(
        user,
        tokens.access_token,
        tokens.refresh_token,
        access_expires_at,
    )


def _build_response(
    user: User,
    access_token: str,
    refresh_token: str,
    access_expires_at: datetime,
) -> AccessRefreshDTO:
    expires_in = max(
        0,
        int(access_expires_at.timestamp()) - int(utc_now().timestamp()),
    )
    return AccessRefreshDTO(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserDTO.model_validate(user),
    )
