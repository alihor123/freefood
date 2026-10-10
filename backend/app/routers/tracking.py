"""Маршруты правил отслеживания скидок."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.dependencies import get_current_user
from app.schemas.tracking_schemas import (
    TrackingCreate,
    TrackingListResponse,
    TrackingPatch,
    TrackingRead,
)


tracking_router = APIRouter(prefix="/tracking", tags=["Отслеживание"])

_NOT_IMPLEMENTED = {
    status.HTTP_501_NOT_IMPLEMENTED: {
        "description": "Хранилище правил отслеживания пока не подключено."
    }
}


@tracking_router.get(
    "",
    response_model=TrackingListResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Список отслеживаний",
    description=(
        "Возвращает правила текущего пользователя с пагинацией. Каждое правило относится "
        "к одному товару либо к одной категории и содержит порог скидки и состояние. "
        "Требуется авторизация."
    ),
)
async def get_tracking(
    page: int = Query(default=1, ge=1, description="Номер страницы, начиная с 1"),
    page_size: int = Query(
        default=20, ge=1, le=100, description="Количество правил на странице (до 100)"
    ),
    _auth_context=Depends(get_current_user),
) -> TrackingListResponse:
    """Получить правила текущего пользователя."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Получение правил отслеживания пока не реализовано.",
    )


@tracking_router.post(
    "",
    response_model=TrackingRead,
    status_code=status.HTTP_201_CREATED,
    responses=_NOT_IMPLEMENTED,
    summary="Создать отслеживание",
    description=(
        "Создаёт правило для одного товара или одной категории в выбранном магазине. "
        "Укажите ровно один из `product_id` и `category_id`, а также минимальный процент "
        "скидки. По умолчанию правило включено. Требуется авторизация."
    ),
)
async def create_tracking(
    payload: TrackingCreate,
    _auth_context=Depends(get_current_user),
) -> TrackingRead:
    """Создать правило скидки для текущего пользователя."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Создание правила отслеживания пока не реализовано.",
    )


@tracking_router.get(
    "/{tracking_id}",
    response_model=TrackingRead,
    responses=_NOT_IMPLEMENTED,
    summary="Получить отслеживание",
    description=(
        "Возвращает правило текущего пользователя. Правило другого пользователя не "
        "раскрывается. Требуется авторизация."
    ),
)
async def get_tracking_by_id(
    tracking_id: int = Path(gt=0, description="Положительный идентификатор правила"),
    _auth_context=Depends(get_current_user),
) -> TrackingRead:
    """Получить одно правило текущего пользователя."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Получение правила отслеживания пока не реализовано.",
    )


@tracking_router.patch(
    "/{tracking_id}",
    response_model=TrackingRead,
    responses=_NOT_IMPLEMENTED,
    summary="Изменить отслеживание",
    description=(
        "Обновляет порог скидки и/или состояние правила. Магазин и отслеживаемый объект "
        "после создания не меняются; пустой запрос недопустим. Требуется авторизация."
    ),
)
async def update_tracking(
    payload: TrackingPatch,
    tracking_id: int = Path(gt=0, description="Положительный идентификатор правила"),
    _auth_context=Depends(get_current_user),
) -> TrackingRead:
    """Изменить только порог скидки или состояние правила."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Изменение правила отслеживания пока не реализовано.",
    )


@tracking_router.delete(
    "/{tracking_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses=_NOT_IMPLEMENTED,
    summary="Удалить отслеживание",
    description="Удаляет правило текущего пользователя. Требуется авторизация.",
)
async def delete_tracking(
    tracking_id: int = Path(gt=0, description="Положительный идентификатор правила"),
    _auth_context=Depends(get_current_user),
) -> None:
    """Удалить правило текущего пользователя."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Удаление правила отслеживания пока не реализовано.",
    )
