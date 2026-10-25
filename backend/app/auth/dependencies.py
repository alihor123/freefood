from authx import TokenPayload
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import get_active_session
from app.auth.tokens import security
from app.database import get_db


async def get_current_user(
    payload: TokenPayload = Depends(security.access_token_required),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Проверяет сессию и возвращает пользователя после проверки JWT в AuthX."""
    _, user = await get_active_session(payload, db)
    return user
