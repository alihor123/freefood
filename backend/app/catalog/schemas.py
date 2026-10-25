"""DTO каталога для будущих ответов API."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StoreRead(BaseModel):
    """Магазин, доступный в каталоге."""

    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    logo_url: str | None = None
    is_active: bool


class StoreListResponse(BaseModel):
    """Список магазинов каталога."""

    items: list[StoreRead]
    total: int = Field(ge=0)


class CategoryRead(BaseModel):
    """Категория товаров магазина."""

    id: int = Field(gt=0)
    store_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    product_count: int | None = Field(default=None, ge=0)


class CategoryListResponse(BaseModel):
    """Список категорий каталога."""

    items: list[CategoryRead]
    total: int = Field(ge=0)


class ProductSummary(BaseModel):
    """Поля товара, необходимые для выдачи каталога."""

    id: int = Field(gt=0)
    store_id: int = Field(gt=0)
    category_id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1)
    image_url: str | None = None
    current_price: Decimal = Field(ge=0)
    previous_price: Decimal | None = Field(default=None, ge=0)
    discount_percent: Decimal | None = Field(default=None, ge=0, le=100)
    in_stock: bool
    availability: str | None = None
    last_checked: datetime | None = None


class ProductDetail(ProductSummary):
    """Подробная карточка товара."""

    description: str | None = None


class ProductListResponse(BaseModel):
    """Страница каталога с общим количеством найденных товаров."""

    items: list[ProductSummary]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    pages: int = Field(ge=0)
