import hashlib
from datetime import datetime, timedelta
from uuid import UUID

from authx import AuthX, AuthXConfig, RequestToken
from authx.exceptions import AuthXException
from fastapi import HTTPException

from app.config import settings


security = AuthX(
    AuthXConfig(
        JWT_SECRET_KEY=settings.JWT_SECRET_KEY,
        JWT_ALGORITHM="HS256",
        JWT_DECODE_ALGORITHMS=["HS256"],
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=settings.JWT_REFRESH_TTL_DAYS),
        JWT_TOKEN_LOCATION=["headers", "cookies"],
        JWT_COOKIE_SECURE=settings.JWT_COOKIE_SECURE,
        JWT_COOKIE_SAMESITE=settings.JWT_COOKIE_SAMESITE,
    )
)


def create_token_pair(
    user_id: int,
    session_id: str,
) -> tuple[str, str, datetime, datetime]:
    """Выпускает access и refresh для одной сессии."""
    data = {"session_id": session_id}
    access_token = security.create_access_token(uid=str(user_id), data=data)
    refresh_token = security.create_refresh_token(uid=str(user_id), data=data)

    access = security.verify_token(
        RequestToken(token=access_token, type="access", location="headers")
    )
    refresh = security.verify_token(
        RequestToken(token=refresh_token, type="refresh", location="json")
    )
    return (
        access_token,
        refresh_token,
        access.expiry_datetime,
        refresh.expiry_datetime,
    )


def verify_access_token(
    token: RequestToken,
    verify_csrf: bool = True,
) -> tuple[int, str]:
    """Проверяет access через AuthX и возвращает ID пользователя и сессии."""
    payload = _verify(token, verify_csrf)
    return _read_claims(payload.sub, getattr(payload, "session_id", None))


def verify_refresh_token(token: RequestToken) -> tuple[int, str]:
    """Проверяет refresh через AuthX и возвращает ID пользователя и сессии."""
    payload = _verify(token)
    return _read_claims(payload.sub, getattr(payload, "session_id", None))


def hash_token(token: str) -> str:
    """Возвращает SHA-256 хеш токена для хранения в БД."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _verify(token: RequestToken, verify_csrf: bool = True):
    try:
        return security.verify_token(token, verify_csrf=verify_csrf)
    except AuthXException:
        raise unauthorized("Недействительный или истёкший токен") from None


def _read_claims(user_id_claim: str, session_id_claim: object) -> tuple[int, str]:
    try:
        user_id = int(user_id_claim)
        session_id = str(UUID(str(session_id_claim)))
    except (TypeError, ValueError, AttributeError):
        raise unauthorized("Некорректные данные токена") from None

    if user_id <= 0:
        raise unauthorized("Некорректные данные токена")

    return user_id, session_id
