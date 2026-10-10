from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(
        min_length=1,
        max_length=16384,
        description="Исходная подписанная строка Telegram.WebApp.initData",
    )


class RefreshRequest(BaseModel):
    refresh_token: str = Field(
        min_length=1,
        max_length=8192,
        description="Текущий refresh-токен; после успешного обмена использовать новый",
    )


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int
    telegram_id: int
    username: str | None
    first_name: str
    last_name: str | None
    language_code: str | None
    created_at: datetime


class AccessRefreshDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserDTO


class LogoutDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    message: str = "Выход выполнен"
