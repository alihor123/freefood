"""Заглушки операций отслеживания товаров."""


async def list_tracking(user_id: int, *, page: int, page_size: int):
    """Вернуть страницу правил пользователя."""
    raise NotImplementedError("Хранилище правил отслеживания ещё не подключено")


async def get_tracking(user_id: int, tracking_id: int):
    """Вернуть правило пользователя."""
    raise NotImplementedError("Хранилище правил отслеживания ещё не подключено")


async def create_tracking(user_id: int, payload):
    """Создать правило пользователя."""
    raise NotImplementedError("Хранилище правил отслеживания ещё не подключено")


async def update_tracking(user_id: int, tracking_id: int, payload):
    """Изменить порог скидки или состояние правила."""
    raise NotImplementedError("Хранилище правил отслеживания ещё не подключено")


async def delete_tracking(user_id: int, tracking_id: int):
    """Удалить правило пользователя."""
    raise NotImplementedError("Хранилище правил отслеживания ещё не подключено")
