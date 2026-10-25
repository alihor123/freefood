import logging

from authx.exceptions import (
    JWTDecodeError,
    NoAuthorizationError,
    TokenError,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


async def auth_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Преобразует ошибки проверки JWT в единый HTTP-ответ."""
    logger.info("HTTP 401 %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=401,
        content={"detail": "Недействительный или истёкший токен"},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Записывает traceback на сервере и возвращает общее сообщение клиенту."""
    logger.error(
        "Ошибка при обработке %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Внутренняя ошибка сервера"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    for exception in (JWTDecodeError, TokenError, NoAuthorizationError):
        app.add_exception_handler(exception, auth_exception_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)
