import hashlib
import hmac
import importlib
import json
import os
import secrets
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_BOT_TOKEN = f"test-bot-{secrets.token_urlsafe(48)}"
TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"freefood-auth-{uuid4().hex}.db"

# Тесты подставляют собственные секреты и БД до импорта приложения.
os.environ.update(
    {
        "JWT_SECRET_KEY": f"test-jwt-{secrets.token_urlsafe(48)}",
        "TELEGRAM_BOT_TOKEN": TEST_BOT_TOKEN,
        "DATABASE_NAME": str(TEST_DATABASE_PATH),
        "JWT_ACCESS_TTL_MINUTES": "10",
        "JWT_REFRESH_TTL_DAYS": "7",
        "JWT_COOKIE_SECURE": "false",
        "JWT_COOKIE_SAMESITE": "lax",
        "TELEGRAM_CHECK_INIT_DATA_AGE": "true",
        "TELEGRAM_INIT_DATA_TTL_SECONDS": "300",
        "TELEGRAM_CLOCK_SKEW_SECONDS": "30",
        "SESSION_CLEANUP_ENABLED": "false",
    }
)

database_module = importlib.import_module("app.database.database")
models_module = importlib.import_module("app.database.models")
main_module = importlib.import_module("app.main")

AsyncSessionLocal = database_module.AsyncSessionLocal
AuthSession = models_module.AuthSession
User = models_module.User
app = main_module.app


def build_init_data(
    *,
    telegram_id: int = 123456789,
    auth_date: int | str | None = None,
    user: dict | None = None,
    extra: dict[str, str] | None = None,
) -> str:
    """Подписывает тестовые initData фиктивным ключом бота."""
    if auth_date is None:
        auth_date = int(time.time())
    if user is None:
        user = {
            "id": telegram_id,
            "first_name": "Тестовый пользователь",
            "last_name": "Проверка",
            "username": "freefood_test",
            "language_code": "ru",
        }

    data = {
        "auth_date": str(auth_date),
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
    }
    if extra:
        data.update(extra)

    check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(
        b"WebAppData",
        TEST_BOT_TOKEN.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature = hmac.new(
        secret_key,
        check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode([*data.items(), ("hash", signature)])


async def _clear_database() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(AuthSession))
        await db.execute(delete(User))
        await db.commit()


@pytest.fixture(scope="session")
def client():
    """Применяет реальные миграции и поднимает приложение на тестовой БД."""
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    try:
        command.upgrade(alembic_config, "head")
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        for suffix in ("", "-wal", "-shm"):
            Path(f"{TEST_DATABASE_PATH}{suffix}").unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def isolate_database(client: TestClient):
    """Очищает пользовательские данные до и после каждого теста."""
    client.cookies.clear()
    client.portal.call(_clear_database)
    yield
    client.cookies.clear()
    client.portal.call(_clear_database)


@pytest.fixture
def init_data_factory():
    return build_init_data
