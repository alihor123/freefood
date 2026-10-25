from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class NotificationCreate(BaseModel):
    """Данные события перед сохранением уведомления."""

    user_id: int = Field(gt=0)
    rule_id: int | None = Field(default=None, gt=0)
    product_id: int | None = Field(default=None, gt=0)
    product_name: str = Field(min_length=1, max_length=255)
    store_name: str = Field(min_length=1, max_length=128)
    price_kopecks: int | None = Field(default=None, ge=0)
    discount_percent: Decimal = Field(ge=0, le=100)
    threshold_percent: Decimal = Field(ge=0, le=100)
    status: Literal["pending", "sent", "failed", "cancelled"] = "pending"
    attempts: int = Field(default=0, ge=0)
