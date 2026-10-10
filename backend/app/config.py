from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения и локального .env."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    JWT_SECRET_KEY: str
    TELEGRAM_BOT_TOKEN: str
    JWT_ACCESS_TTL_MINUTES: int = 10
    JWT_REFRESH_TTL_DAYS: int = 7
    JWT_COOKIE_SECURE: bool = True
    JWT_COOKIE_SAMESITE: str = "lax"

    TELEGRAM_CHECK_INIT_DATA_AGE: bool = True
    TELEGRAM_INIT_DATA_TTL_SECONDS: int = 300
    TELEGRAM_CLOCK_SKEW_SECONDS: int = 30

    DATABASE_NAME: str = "freefood.db"
    SESSION_CLEANUP_ENABLED: bool = True
    SESSION_CLEANUP_INTERVAL_HOURS: int = 24

    @property
    def get_database_url(self) -> str:
        """Строит URL SQLite независимо от папки, из которой запущен сервер."""
        database_path = Path(self.DATABASE_NAME)
        if not database_path.is_absolute():
            database_path = BACKEND_DIR / database_path
        return f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}"


settings = Settings()
