"""Заглушки операций каталога."""


async def list_stores():
    """Вернуть магазины каталога."""
    raise NotImplementedError("Источник магазинов каталога ещё не подключён")


async def list_categories(store_id: int | None = None):
    """Вернуть категории каталога."""
    raise NotImplementedError("Источник категорий каталога ещё не подключён")


async def list_products(**filters):
    """Вернуть страницу товаров каталога."""
    raise NotImplementedError("Источник товаров каталога ещё не подключён")


async def get_product(product_id: int):
    """Вернуть карточку товара."""
    raise NotImplementedError("Источник карточек товаров ещё не подключён")
