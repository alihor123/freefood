"""DTO пользовательских правил отслеживания скидок."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class TrackingCreate(BaseModel):
    """Данные для создания отслеживания одного товара или категории."""

    store_id: int = Field(gt=0)
    product_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    min_discount_percent: Decimal = Field(ge=0, le=100)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_target(self) -> "TrackingCreate":
        """Для правила выбирается ровно один товар или одна категория."""
        if (self.product_id is None) == (self.category_id is None):
            raise ValueError(
                "Нужно указать ровно одно поле: product_id или category_id"
            )
        return self


class TrackingPatch(BaseModel):
    """Порог скидки и состояние правила для изменения."""

    min_discount_percent: Decimal | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> "TrackingPatch":
        """Не разрешает пустое обновление и явное обнуление порога скидки."""
        if not self.model_fields_set:
            raise ValueError("Нужно передать хотя бы одно изменяемое поле")
        if (
            "min_discount_percent" in self.model_fields_set
            and self.min_discount_percent is None
        ):
            raise ValueError("min_discount_percent не может быть null")
        if "is_active" in self.model_fields_set and self.is_active is None:
            raise ValueError("is_active не может быть null")
        return self


class TrackingRead(BaseModel):
    """Правило отслеживания, принадлежащее текущему пользователю."""

    id: int = Field(gt=0)
    store_id: int = Field(gt=0)
    product_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    min_discount_percent: Decimal = Field(ge=0, le=100)
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "TrackingRead":
        """Проверить, что правило относится к одному товару или категории."""
        if (self.product_id is None) == (self.category_id is None):
            raise ValueError(
                "Нужно указать ровно одно поле: product_id или category_id"
            )
        return self


class TrackingListResponse(BaseModel):
    """Список правил отслеживания текущего пользователя."""

    items: list[TrackingRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
