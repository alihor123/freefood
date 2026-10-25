from datetime import datetime, timedelta

from authx import AuthX, AuthXConfig, TokenResponse

from app.config import settings
from app.database import utc_now


security = AuthX(
    AuthXConfig(
        JWT_SECRET_KEY=settings.JWT_SECRET_KEY,
        JWT_ALGORITHM="HS256",
        JWT_DECODE_ALGORITHMS=["HS256"],
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
        JWT_TOKEN_LOCATION=["json", "cookies", "headers"],
        JWT_ACCESS_COOKIE_PATH="/api",
        JWT_REFRESH_COOKIE_PATH="/api/auth/refresh",
        JWT_COOKIE_SECURE=settings.JWT_COOKIE_SECURE,
        JWT_COOKIE_SAMESITE=settings.JWT_COOKIE_SAMESITE,
        JWT_COOKIE_HTTP_ONLY=True,
        JWT_COOKIE_CSRF_PROTECT=False,
    )
)


def create_session_token_pair(
    user_id: int,
    session_id: str,
) -> tuple[TokenResponse, datetime, datetime]:
    """Выпускает пару AuthX с ID сессии и возвращает её сроки действия."""
    now = utc_now()
    access_expires_at = now + security.config.JWT_ACCESS_TOKEN_EXPIRES
    refresh_expires_at = now + security.config.JWT_REFRESH_TOKEN_EXPIRES
    tokens = security.create_token_pair(
        uid=str(user_id),
        data={"session_id": session_id},
        access_expiry=access_expires_at,
        refresh_expiry=refresh_expires_at,
    )
    return tokens, access_expires_at, refresh_expires_at
