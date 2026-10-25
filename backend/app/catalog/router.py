"""Маршруты каталога."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query

from app.catalog.schemas import (
    CategoryListResponse,
    ProductDetail,
    ProductListResponse,
    StoreListResponse,
)


catalog_router = APIRouter(tags=["Каталог"])


@catalog_router.get("/stores", response_model=StoreListResponse)
async def get_stores() -> StoreListResponse:
    """Список магазинов каталога."""
    raise HTTPException(
        status_code=501,
        detail="Получение списка магазинов пока не реализовано.",
    )


@catalog_router.get("/categories", response_model=CategoryListResponse)
async def get_categories(
    store_id: int | None = Query(default=None, gt=0),
) -> CategoryListResponse:
    """Категории каталога."""
    raise HTTPException(
        status_code=501,
        detail="Получение категорий пока не реализовано.",
    )


@catalog_router.get("/products", response_model=ProductListResponse)
async def get_products(
    search: str | None = Query(default=None, min_length=1, max_length=200),
    store_id: int | None = Query(default=None, gt=0),
    category_id: int | None = Query(default=None, gt=0),
    min_discount_percent: Decimal | None = Query(default=None, ge=0, le=100),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    in_stock: bool | None = None,
    sort: Literal[
        "discount_desc", "price_asc", "price_desc", "recently_checked"
    ] = "discount_desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ProductListResponse:
    """Страница товаров по заданным фильтрам."""
    raise HTTPException(
        status_code=501,
        detail="Поиск и фильтрация товаров пока не реализованы.",
    )


@catalog_router.get("/products/{product_id}", response_model=ProductDetail)
async def get_product(
    product_id: int = Path(gt=0),
) -> ProductDetail:
    """Карточка товара."""
    raise HTTPException(
        status_code=501,
        detail="Получение карточки товара пока не реализовано.",
    )
