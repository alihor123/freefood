from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User


async def get_user_by_id(user_id: int, db: AsyncSession) -> User | None:
    return await db.scalar(select(User).where(User.id == user_id))


async def get_or_create_telegram_user(
    identity: dict[str, int | str | None],
    db: AsyncSession,
) -> User:
    """Находит пользователя по Telegram ID или создаёт его при первом входе."""
    statement = insert(User).values(
        telegram_id=identity["telegram_id"],
        username=identity["username"],
        first_name=identity["first_name"],
        last_name=identity["last_name"],
        language_code=identity["language_code"],
    )
    await db.execute(
        statement.on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={
                "username": identity["username"],
                "first_name": identity["first_name"],
                "last_name": identity["last_name"],
                "language_code": identity["language_code"],
            },
        )
    )

    user = await db.scalar(
        select(User).where(User.telegram_id == identity["telegram_id"])
    )
    if user is None:
        raise RuntimeError("Telegram user upsert did not return a user")
    return user
