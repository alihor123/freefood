"""Данные товара из адаптера магазина."""

from decimal import Decimal

from pydantic import BaseModel, Field


class ProductData(BaseModel):
    """Нормализованные данные товара магазина."""

    external_id: str = Field(min_length=1, max_length=128)
    external_category_id: str | None = Field(default=None, min_length=1, max_length=128)
    category_name: str | None = Field(default=None, min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    image_url: str | None = None
    source_url: str | None = None
    current_price_kopecks: int | None = Field(default=None, ge=0)
    previous_price_kopecks: int | None = Field(default=None, ge=0)
    discount_percent: Decimal | None = Field(default=None, ge=0, le=100)
    in_stock: bool | None = None
