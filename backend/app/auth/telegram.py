import hashlib
import hmac
import json
import re
import time
from urllib.parse import parse_qsl

from app.config import settings


def verify_telegram_init_data(
    init_data: str,
) -> dict[str, int | str | None] | None:
    """Проверяет подпись Telegram и извлекает данные пользователя."""
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None

    data: dict[str, str] = {}
    for key, value in pairs:
        if not key or key in data:
            return None
        data[key] = value

    received_hash = data.pop("hash", None)
    if received_hash is None or re.fullmatch(r"[0-9a-f]{64}", received_hash) is None:
        return None

    secret_key = hmac.new(
        b"WebAppData",
        settings.TELEGRAM_BOT_TOKEN.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    expected_hash = hmac.new(
        secret_key,
        check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        return None

    auth_date_value = data.get("auth_date", "")
    if re.fullmatch(r"[0-9]{1,12}", auth_date_value) is None:
        return None
    auth_date = int(auth_date_value)
    if auth_date <= 0:
        return None
    if settings.TELEGRAM_CHECK_INIT_DATA_AGE:
        now = int(time.time())
        if auth_date < now - settings.TELEGRAM_INIT_DATA_TTL_SECONDS:
            return None
        if auth_date > now + settings.TELEGRAM_CLOCK_SKEW_SECONDS:
            return None

    try:
        telegram_user = json.loads(data.get("user", ""))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(telegram_user, dict):
        return None

    telegram_id = telegram_user.get("id")
    first_name = telegram_user.get("first_name")
    if (
        isinstance(telegram_id, bool)
        or not isinstance(telegram_id, int)
        or telegram_id <= 0
        or not isinstance(first_name, str)
        or not first_name.strip()
    ):
        return None

    values: dict[str, str | None] = {}
    for field in ("last_name", "username", "language_code"):
        value = telegram_user.get(field)
        if value is not None and not isinstance(value, str):
            return None
        values[field] = value

    return {
        "telegram_id": telegram_id,
        "first_name": first_name,
        "last_name": values["last_name"],
        "username": values["username"],
        "language_code": values["language_code"],
    }
