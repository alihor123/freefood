from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.auth.schemas import (
    AccessRefreshDTO,
    TelegramAuthRequest,
    UserDTO,
)
from app.auth.service import login_with_telegram, refresh_tokens
from app.auth.tokens import security
from app.config import settings
from app.database import get_db


auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post("/telegram", response_model=AccessRefreshDTO)
async def telegram_auth(
    body: TelegramAuthRequest,
    response: Response,
    x_device_id: UUID = Header(),
    db: AsyncSession = Depends(get_db),
) -> AccessRefreshDTO:
    """Проверяет initData и создаёт или обновляет сессию устройства."""
    tokens = await login_with_telegram(body.init_data, str(x_device_id), db)
    security.set_access_cookies(
        tokens.access_token, response, max_age=settings.JWT_ACCESS_TTL_MINUTES * 60
    )
    security.set_refresh_cookies(
        tokens.refresh_token,
        response,
        max_age=settings.JWT_REFRESH_TTL_DAYS * 24 * 60 * 60,
    )
    return tokens


@auth_router.post("/refresh", response_model=AccessRefreshDTO)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AccessRefreshDTO:
    """Обновляет пару по JSON-токену или refresh cookie."""
    token = await security.get_refresh_token_from_request(request)
    tokens = await refresh_tokens(token, db)
    security.set_access_cookies(
        tokens.access_token, response, max_age=settings.JWT_ACCESS_TTL_MINUTES * 60
    )
    security.set_refresh_cookies(
        tokens.refresh_token,
        response,
        max_age=settings.JWT_REFRESH_TTL_DAYS * 24 * 60 * 60,
    )
    return tokens


@auth_router.get("/me", response_model=UserDTO)
async def me(user: User = Depends(get_current_user)) -> UserDTO:
    """Возвращает профиль текущей сессии."""
    return UserDTO.model_validate(user)
