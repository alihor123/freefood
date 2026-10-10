"""DTO каталога для будущих ответов API."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StoreRead(BaseModel):
    """Магазин, доступный в каталоге."""

    id: int = Field(gt=0, description="Идентификатор магазина")
    name: str = Field(min_length=1, description="Название магазина")
    logo_url: str | None = Field(default=None, description="Ссылка на логотип")
    is_active: bool = Field(description="Участвует ли магазин в обновлении каталога")


class StoreListResponse(BaseModel):
    """Список магазинов каталога."""

    items: list[StoreRead]
    total: int = Field(ge=0, description="Количество магазинов в ответе")


class CategoryRead(BaseModel):
    """Категория товаров магазина."""

    id: int = Field(gt=0, description="Идентификатор категории")
    store_id: int = Field(gt=0, description="Магазин, которому принадлежит категория")
    name: str = Field(min_length=1, description="Название категории")
    product_count: int | None = Field(
        default=None, ge=0, description="Количество товаров"
    )


class CategoryListResponse(BaseModel):
    """Список категорий каталога."""

    items: list[CategoryRead]
    total: int = Field(ge=0, description="Количество категорий в ответе")


class ProductSummary(BaseModel):
    """Поля товара, необходимые для выдачи каталога."""

    id: int = Field(gt=0, description="Идентификатор товара")
    store_id: int = Field(gt=0, description="Магазин")
    category_id: int | None = Field(default=None, gt=0, description="Категория")
    name: str = Field(min_length=1, description="Название товара")
    image_url: str | None = Field(default=None, description="Основное изображение")
    current_price: Decimal = Field(ge=0, description="Текущая цена")
    previous_price: Decimal | None = Field(
        default=None, ge=0, description="Цена до скидки"
    )
    discount_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Размер скидки в процентах",
    )
    in_stock: bool = Field(description="Есть ли товар в наличии")
    availability: str | None = Field(
        default=None, description="Текстовый статус наличия"
    )
    last_checked: datetime | None = Field(
        default=None, description="Время последней проверки цены"
    )


class ProductDetail(ProductSummary):
    """Подробная карточка товара."""

    description: str | None = Field(default=None, description="Описание товара")


class ProductListResponse(BaseModel):
    """Страница каталога с общим количеством найденных товаров."""

    items: list[ProductSummary]
    total: int = Field(ge=0, description="Общее количество товаров по фильтру")
    page: int = Field(ge=1, description="Номер страницы")
    page_size: int = Field(ge=1, description="Размер страницы")
    pages: int = Field(ge=0, description="Количество страниц")
