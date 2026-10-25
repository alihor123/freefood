"""Маршруты пользовательских отслеживаний."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.tracking.schemas import (
    TrackingCreate,
    TrackingListResponse,
    TrackingPatch,
    TrackingRead,
)


tracking_router = APIRouter(prefix="/tracking", tags=["Отслеживание"])


@tracking_router.get("", response_model=TrackingListResponse)
async def get_tracking(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
) -> TrackingListResponse:
    """Список правил текущего пользователя."""
    raise HTTPException(
        status_code=501,
        detail="Получение правил отслеживания пока не реализовано.",
    )


@tracking_router.post("", response_model=TrackingRead, status_code=201)
async def create_tracking(
    payload: TrackingCreate,
    _user: User = Depends(get_current_user),
) -> TrackingRead:
    """Создать правило текущего пользователя."""
    raise HTTPException(
        status_code=501,
        detail="Создание правила отслеживания пока не реализовано.",
    )


@tracking_router.get("/{tracking_id}", response_model=TrackingRead)
async def get_tracking_by_id(
    tracking_id: int = Path(gt=0),
    _user: User = Depends(get_current_user),
) -> TrackingRead:
    """Одно правило текущего пользователя."""
    raise HTTPException(
        status_code=501,
        detail="Получение правила отслеживания пока не реализовано.",
    )


@tracking_router.patch("/{tracking_id}", response_model=TrackingRead)
async def update_tracking(
    payload: TrackingPatch,
    tracking_id: int = Path(gt=0),
    _user: User = Depends(get_current_user),
) -> TrackingRead:
    """Обновить порог или активность правила."""
    raise HTTPException(
        status_code=501,
        detail="Изменение правила отслеживания пока не реализовано.",
    )


@tracking_router.delete(
    "/{tracking_id}",
    status_code=204,
    response_model=None,
)
async def delete_tracking(
    tracking_id: int = Path(gt=0),
    _user: User = Depends(get_current_user),
) -> None:
    """Удалить правило текущего пользователя."""
    raise HTTPException(
        status_code=501,
        detail="Удаление правила отслеживания пока не реализовано.",
    )
