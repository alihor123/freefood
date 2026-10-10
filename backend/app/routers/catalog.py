"""Публичные маршруты каталога товаров."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.schemas.catalog_schemas import (
    CategoryListResponse,
    ProductDetail,
    ProductListResponse,
    StoreListResponse,
)


catalog_router = APIRouter(prefix="", tags=["Каталог"])

_NOT_IMPLEMENTED = {
    status.HTTP_501_NOT_IMPLEMENTED: {
        "description": "Маршрут описан, но источник каталога пока не подключён."
    }
}


@catalog_router.get(
    "/stores",
    response_model=StoreListResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Получить магазины",
    description=(
        "Возвращает магазины, доступные в каталоге, с общим количеством записей. "
        "Маршрут публичный и не требует авторизации."
    ),
)
async def get_stores() -> StoreListResponse:
    """Получить список доступных магазинов."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Получение списка магазинов пока не реализовано.",
    )


@catalog_router.get(
    "/categories",
    response_model=CategoryListResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Получить категории",
    description=(
        "Возвращает категории каталога. Если передан `store_id`, список ограничивается "
        "категориями выбранного магазина. Маршрут публичный."
    ),
)
async def get_categories(
    store_id: int | None = Query(
        default=None,
        gt=0,
        description="Необязательный идентификатор магазина для фильтрации категорий",
    ),
) -> CategoryListResponse:
    """Получить все категории или категории одного магазина."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Получение категорий пока не реализовано.",
    )


@catalog_router.get(
    "/products",
    response_model=ProductListResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Найти товары",
    description=(
        "Возвращает страницу товаров с ценой, прежней ценой, скидкой, наличием и временем "
        "последней проверки. Поддерживаются поиск по названию и фильтры по магазину, "
        "категории, скидке, цене и наличию. Сортировка применяется до пагинации. "
        "Маршрут публичный."
    ),
)
async def get_products(
    search: str | None = Query(
        default=None, min_length=1, max_length=200, description="Часть названия товара"
    ),
    store_id: int | None = Query(
        default=None, gt=0, description="Ограничить выдачу одним магазином"
    ),
    category_id: int | None = Query(
        default=None, gt=0, description="Ограничить выдачу одной категорией"
    ),
    min_discount_percent: Decimal | None = Query(
        default=None,
        ge=0,
        le=100,
        description="Минимальный размер скидки, от 0 до 100 процентов",
    ),
    min_price: Decimal | None = Query(
        default=None, ge=0, description="Минимальная текущая цена"
    ),
    max_price: Decimal | None = Query(
        default=None, ge=0, description="Максимальная текущая цена"
    ),
    in_stock: bool | None = Query(
        default=None, description="Оставить товары в наличии или отсутствующие"
    ),
    sort: Literal[
        "discount_desc", "price_asc", "price_desc", "recently_checked"
    ] = Query(
        default="discount_desc",
        description="Сортировка: скидка, цена по возрастанию/убыванию или свежесть проверки",
    ),
    page: int = Query(default=1, ge=1, description="Номер страницы, начиная с 1"),
    page_size: int = Query(
        default=20, ge=1, le=100, description="Количество товаров на странице (до 100)"
    ),
) -> ProductListResponse:
    """Получить страницу каталога с фильтрами и сортировкой."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Поиск и фильтрация товаров пока не реализованы.",
    )


@catalog_router.get(
    "/products/{product_id}",
    response_model=ProductDetail,
    responses=_NOT_IMPLEMENTED,
    summary="Получить карточку товара",
    description=(
        "Возвращает подробные поля товара, включая актуальную цену, прежнюю цену, "
        "размер скидки, наличие и время последней проверки. Маршрут публичный."
    ),
)
async def get_product(
    product_id: int = Path(gt=0, description="Положительный идентификатор товара"),
) -> ProductDetail:
    """Получить карточку товара по идентификатору."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Получение карточки товара пока не реализовано.",
    )
