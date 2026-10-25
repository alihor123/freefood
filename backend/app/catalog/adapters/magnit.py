"""Заготовки адаптера магазина Магнит."""

from app.catalog.adapters.schemas import ProductData


async def request() -> list[dict[str, object]]:
    """Получить сырые данные каталога с пагинацией."""
    raise NotImplementedError


def parse_product(raw: dict[str, object]) -> ProductData:
    """Преобразовать одну карточку товара Магнита."""
    raise NotImplementedError
