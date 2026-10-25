"""add_session_device_id

Revision ID: 20261025_0002
Revises: 20261010_0001
Create Date: 2026-10-25 06:21:46.493610

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20261025_0002'
down_revision: Union[str, Sequence[str], None] = '20261010_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет ID устройства и уникальность сессии пользователя на нём."""
    op.add_column(
        "auth_sessions", sa.Column("device_id", sa.String(36), nullable=True)
    )
    # У старых сессий устройство неизвестно, сохраняем уникальное временное значение.
    op.execute("UPDATE auth_sessions SET device_id = id")
    with op.batch_alter_table("auth_sessions") as batch_op:
        batch_op.alter_column("device_id", existing_type=sa.String(36), nullable=False)
        batch_op.create_unique_constraint(
            "uq_auth_sessions_user_device", ["user_id", "device_id"]
        )


def downgrade() -> None:
    """Убирает привязку к устройству без удаления пользователей и сессий."""
    with op.batch_alter_table("auth_sessions") as batch_op:
        batch_op.drop_constraint("uq_auth_sessions_user_device", type_="unique")
        batch_op.drop_column("device_id")
