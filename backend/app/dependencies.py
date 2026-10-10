from authx import RequestToken
from authx.exceptions import AuthXException
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.services.auth_service import authenticate_access_token
from app.services.token_service import security, unauthorized


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Проверяет Bearer или access cookie и возвращает пользователя сессии."""
    if credentials is not None:
        token = RequestToken(
            token=credentials.credentials,
            type="access",
            location="headers",
        )
        verify_csrf = False
    else:
        authorization = request.headers.get("authorization", "")
        if authorization.partition(" ")[0].lower() == "bearer":
            raise unauthorized("Недействительный или истёкший токен")
        try:
            token = await security.get_access_token_from_request(
                request,
                locations=["cookies"],
            )
        except AuthXException:
            raise unauthorized("Требуется токен авторизации") from None
        verify_csrf = request.method.upper() in security.config.JWT_CSRF_METHODS

    return await authenticate_access_token(token, db, verify_csrf)
