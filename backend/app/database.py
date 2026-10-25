from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy import DateTime, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.config import settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Возвращает даты SQLite с явно указанным часовым поясом UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, _dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, _dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.get_database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite требует включать внешние ключи отдельно для каждого соединения."""
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


async def get_db() -> AsyncIterator[AsyncSession]:
    """Открывает сессию БД на время запроса и закрывает после него."""
    async with AsyncSessionLocal() as db:
        yield db
