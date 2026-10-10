"""DTO пользовательских правил отслеживания скидок."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


DiscountPercent = Decimal


class TrackingCreate(BaseModel):
    """Данные для создания отслеживания одного товара или категории."""

    store_id: int = Field(gt=0, description="Магазин, в котором отслеживается объект")
    product_id: int | None = Field(
        default=None, gt=0, description="Товар для отслеживания"
    )
    category_id: int | None = Field(
        default=None, gt=0, description="Категория для отслеживания"
    )
    min_discount_percent: DiscountPercent = Field(
        ge=0,
        le=100,
        description="Минимальный размер скидки для уведомления",
    )
    is_active: bool = Field(default=True, description="Включено ли отслеживание")

    @model_validator(mode="after")
    def validate_target(self) -> "TrackingCreate":
        """Для правила выбирается ровно один товар или одна категория."""
        if (self.product_id is None) == (self.category_id is None):
            raise ValueError(
                "Нужно указать ровно одно поле: product_id или category_id"
            )
        return self


class TrackingPatch(BaseModel):
    """Изменяемые поля правила; объект отслеживания после создания неизменяем."""

    min_discount_percent: DiscountPercent | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Новый минимальный размер скидки",
    )
    is_active: bool | None = Field(
        default=None, description="Новое состояние отслеживания"
    )

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

    id: int = Field(gt=0, description="Идентификатор правила")
    store_id: int = Field(gt=0, description="Магазин")
    product_id: int | None = Field(
        default=None, gt=0, description="Отслеживаемый товар"
    )
    category_id: int | None = Field(
        default=None, gt=0, description="Отслеживаемая категория"
    )
    min_discount_percent: DiscountPercent = Field(
        ge=0, le=100, description="Порог скидки"
    )
    is_active: bool = Field(description="Включено ли отслеживание")
    created_at: datetime = Field(description="Время создания правила")
    updated_at: datetime | None = Field(
        default=None, description="Время последнего изменения"
    )

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
    total: int = Field(ge=0, description="Количество правил в ответе")
    page: int = Field(ge=1, description="Номер страницы")
    page_size: int = Field(ge=1, description="Размер страницы")
