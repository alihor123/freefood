from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app.config import settings
from app.database.database import engine
from app.routers.auth import auth_router
from app.routers.catalog import catalog_router
from app.routers.tracking import tracking_router
from app.services.token_service import security
from app.tasks.cleanup import cleanup_old_sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Проверяет миграции и управляет планировщиком очистки сессий."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
        if not {"users", "auth_sessions"}.issubset(tables):
            raise RuntimeError(
                "Схема БД не создана. Выполните: uv run alembic upgrade head"
            )

        if settings.SESSION_CLEANUP_ENABLED:
            await cleanup_old_sessions()
            scheduler.add_job(
                cleanup_old_sessions,
                "interval",
                hours=settings.SESSION_CLEANUP_INTERVAL_HOURS,
                id="cleanup_auth_sessions",
                max_instances=1,
                coalesce=True,
            )
            scheduler.start()
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
        await engine.dispose()


app = FastAPI(
    title="Продукты Даром — серверное API",
    description="Авторизация реализована. Методы каталога и отслеживания пока возвращают HTTP 501.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-TOKEN"],
)
security.handle_errors(app)


app.include_router(auth_router, prefix="/api")
app.include_router(catalog_router, prefix="/api")
app.include_router(tracking_router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
    )
