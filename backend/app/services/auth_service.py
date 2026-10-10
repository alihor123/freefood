from datetime import datetime, timezone
from uuid import uuid4

from authx import RequestToken
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AuthSession, User
from app.database.repositories import session_repo, user_repo
from app.schemas.auth_schemas import AccessRefreshDTO, UserDTO
from app.services.telegram_service import verify_telegram_init_data
from app.services.token_service import (
    create_token_pair,
    hash_token,
    unauthorized,
    verify_access_token,
    verify_refresh_token,
)


async def login_with_telegram(init_data: str, db: AsyncSession) -> AccessRefreshDTO:
    """Создаёт сессию для пользователя из проверенных данных Telegram."""
    identity = verify_telegram_init_data(init_data)
    if identity is None:
        raise unauthorized("Данные Telegram недействительны или устарели")

    user = await user_repo.get_or_create_telegram_user(identity, db)
    session_id = str(uuid4())
    tokens = create_token_pair(user.id, session_id)
    _, refresh_token, _, refresh_expires_at = tokens
    db.add(
        AuthSession(
            id=session_id,
            user_id=user.id,
            refresh_token_hash=hash_token(refresh_token),
            expires_at=refresh_expires_at,
        )
    )
    await db.commit()
    return _build_response(user, tokens)


async def refresh_tokens(
    refresh_token: RequestToken,
    db: AsyncSession,
) -> AccessRefreshDTO:
    """Атомарно заменяет текущий refresh и выпускает новую пару токенов."""
    user_id, session_id = verify_refresh_token(refresh_token)
    tokens = create_token_pair(user_id, session_id)
    _, new_refresh_token, _, refresh_expires_at = tokens
    updated = await session_repo.rotate_refresh_token(
        session_id=session_id,
        user_id=user_id,
        old_hash=hash_token(refresh_token.token),
        new_hash=hash_token(new_refresh_token),
        new_expires_at=refresh_expires_at,
        db=db,
    )
    if not updated:
        await db.rollback()
        raise unauthorized("Refresh-токен уже использован или сессия завершена")

    user = await user_repo.get_user_by_id(user_id, db)
    if user is None:
        await db.rollback()
        raise unauthorized("Пользователь не найден")

    await db.commit()
    return _build_response(user, tokens)


async def authenticate_access_token(
    token: RequestToken,
    db: AsyncSession,
    verify_csrf: bool = True,
) -> tuple[User, str]:
    """Проверяет JWT и активную сессию пользователя."""
    user_id, session_id = verify_access_token(token, verify_csrf)
    session = await session_repo.get_active_session(session_id, user_id, db)
    if session is None:
        raise unauthorized("Сессия завершена или не найдена")

    user = await user_repo.get_user_by_id(user_id, db)
    if user is None:
        raise unauthorized("Пользователь не найден")
    return user, session_id


async def logout_session(
    user_id: int,
    session_id: str,
    db: AsyncSession,
) -> None:
    """Отзывает только указанную сессию пользователя."""
    revoked = await session_repo.revoke_session(session_id, user_id, db)
    if not revoked:
        await db.rollback()
        raise unauthorized("Сессия уже завершена или не найдена")
    await db.commit()


def _build_response(
    user: User,
    tokens: tuple[str, str, datetime, datetime],
) -> AccessRefreshDTO:
    access_token, refresh_token, access_expires_at, _ = tokens
    expires_in = max(
        0,
        int(access_expires_at.timestamp())
        - int(datetime.now(timezone.utc).timestamp()),
    )
    return AccessRefreshDTO(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserDTO.model_validate(user),
    )
