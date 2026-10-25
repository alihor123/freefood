"""Маршруты каталога."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.catalog.schemas import (
    CategoryFilters,
    CategoryListResponse,
    ProductDetail,
    ProductFilters,
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
    filters: Annotated[CategoryFilters, Query()],
) -> CategoryListResponse:
    """Категории каталога."""
    raise HTTPException(
        status_code=501,
        detail="Получение категорий пока не реализовано.",
    )


@catalog_router.get("/products", response_model=ProductListResponse)
async def get_products(
    filters: Annotated[ProductFilters, Query()],
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
