from authx import RequestToken
from authx.exceptions import AuthXException
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.database import get_db
from app.dependencies import get_current_user
from app.schemas.auth_schemas import (
    AccessRefreshDTO,
    LogoutDTO,
    RefreshRequest,
    TelegramAuthRequest,
    UserDTO,
)
from app.services.auth_service import (
    login_with_telegram,
    logout_session,
    refresh_tokens,
)
from app.services.token_service import security, unauthorized


auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post(
    "/telegram",
    response_model=AccessRefreshDTO,
    summary="Войти через Telegram",
    description=(
        "Проверяет initData Telegram, находит или создаёт пользователя. "
        "Возвращает пару токенов в JSON и устанавливает HttpOnly cookies "
        "для веб-клиента."
    ),
    responses={401: {"description": "Данные Telegram недействительны или устарели"}},
)
async def telegram_auth(
    body: TelegramAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AccessRefreshDTO:
    """Проверяет initData и создаёт пользователя и сессию при первом входе."""
    tokens = await login_with_telegram(body.init_data, db)
    _set_auth_cookies(response, tokens)
    return tokens


@auth_router.post(
    "/refresh",
    response_model=AccessRefreshDTO,
    summary="Обновить пару токенов",
    description=(
        "Мобильный клиент передаёт refresh_token в JSON. Веб-клиент может "
        "отправить запрос без тела, тогда используется refresh cookie и "
        "заголовок X-CSRF-TOKEN со значением csrf_refresh_token. При успехе "
        "сервер атомарно ротирует токены в той же сессии и возвращает новую "
        "пару в JSON и cookies."
    ),
    responses={
        401: {
            "description": "Refresh недействителен, уже использован или CSRF-проверка не пройдена"
        }
    },
)
async def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> AccessRefreshDTO:
    """Обновляет токены по JSON refresh или cookie с CSRF-проверкой."""
    if body is None:
        try:
            token = await security.get_refresh_token_from_request(
                request,
                locations=["cookies"],
            )
        except AuthXException:
            raise unauthorized("Недействительный или истёкший токен") from None
    else:
        token = RequestToken(
            token=body.refresh_token,
            type="refresh",
            location="json",
        )

    tokens = await refresh_tokens(token, db)
    _set_auth_cookies(response, tokens)
    return tokens


@auth_router.get(
    "/me",
    response_model=UserDTO,
    summary="Получить свой профиль",
    description=(
        "Возвращает пользователя текущей сессии. Явный Bearer имеет приоритет "
        "над access cookie. Запрос GET с cookie не требует CSRF-заголовка."
    ),
    responses={401: {"description": "Access недействителен или сессия отозвана"}},
)
async def me(
    auth_context=Depends(get_current_user),
) -> UserDTO:
    """Возвращает профиль текущей сессии."""
    user, _session_id = auth_context
    return UserDTO.model_validate(user)


@auth_router.post(
    "/logout",
    response_model=LogoutDTO,
    summary="Выйти из текущей сессии",
    description=(
        "Отзывает текущую сессию. Явный Bearer имеет приоритет над access "
        "cookie. Для cookie-запроса нужен заголовок X-CSRF-TOKEN со значением "
        "csrf_access_token. После успешного выхода сервер удаляет auth и CSRF cookies."
    ),
    responses={
        401: {
            "description": "Токен недействителен, сессия завершена или CSRF-проверка не пройдена"
        }
    },
)
async def logout(
    response: Response,
    auth_context=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LogoutDTO:
    """Отзывает текущую сессию и удаляет cookies авторизации."""
    user, session_id = auth_context
    await logout_session(user.id, session_id, db)
    security.unset_cookies(response)
    return LogoutDTO()


def _set_auth_cookies(response: Response, tokens: AccessRefreshDTO) -> None:
    security.set_access_cookies(
        tokens.access_token,
        response,
        max_age=settings.JWT_ACCESS_TTL_MINUTES * 60,
    )
    security.set_refresh_cookies(
        tokens.refresh_token,
        response,
        max_age=settings.JWT_REFRESH_TTL_DAYS * 24 * 60 * 60,
    )
