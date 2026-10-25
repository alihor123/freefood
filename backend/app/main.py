import logging
from contextlib import asynccontextmanager

import uvicorn
from alembic import command
from alembic.config import Config
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter, FastAPI

from app.auth.router import auth_router
from app.catalog.router import catalog_router
from app.config import BACKEND_DIR, settings
from app.database import engine
from app.exceptions import register_exception_handlers
from app.logging_config import setup_logging
from app.tasks.cleanup import cleanup_old_sessions
from app.tracking.router import tracking_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запускает очистку сессий и освобождает ресурсы при остановке."""
    setup_logging()
    logger.info("API запущено")
    scheduler = AsyncIOScheduler(timezone="UTC")
    try:
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
        logger.info("API остановлено")


app = FastAPI(
    title="Продукты Даром — серверное API",
    version="0.1.0",
    lifespan=lifespan,
)
register_exception_handlers(app)

api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router)
api_router.include_router(catalog_router)
api_router.include_router(tracking_router)

app.include_router(api_router)


if __name__ == "__main__":
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
