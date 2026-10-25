from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime, utc_now


class User(Base):
    """Пользователь, найденный по Telegram ID из подписанных initData."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class AuthSession(Base):
    """Одна авторизованная сессия и текущий хеш её refresh-токена."""

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), index=True)
