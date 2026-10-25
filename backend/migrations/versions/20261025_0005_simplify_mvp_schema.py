"""Убирает поля, которые не нужны текущему MVP."""

import sqlalchemy as sa
from alembic import op


revision = "20261025_0005"
down_revision = "20261025_0004"
branch_labels = None
depends_on = None


REMOVED_COLUMNS = {
    "users": ["language_code"],
    "stores": ["created_at"],
    "categories": ["created_at", "updated_at"],
    "products": ["availability", "created_at", "updated_at"],
    "tracking_rules": ["updated_at"],
    "notifications": ["threshold_percent", "attempts", "sent_at", "last_error"],
}


def upgrade() -> None:
    """Сохраняет строки и связи при удалении лишних столбцов."""
    for table, columns in REMOVED_COLUMNS.items():
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.drop_column(column)


def downgrade() -> None:
    """Возвращает столбцы. Удалённые значения восстановить нельзя."""
    columns = {
        "users": [sa.Column("language_code", sa.String(16), nullable=True)],
        "stores": [
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        ],
        "categories": [
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        ],
        "products": [
            sa.Column("availability", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        ],
        "tracking_rules": [
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        ],
        "notifications": [
            sa.Column(
                "threshold_percent",
                sa.Numeric(5, 2),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
            ),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
        ],
    }

    # Временные значения нужны только для существующих строк при откате.
    for table, restored_columns in columns.items():
        with op.batch_alter_table(table, recreate="always") as batch:
            for column in restored_columns:
                batch.add_column(column)
        with op.batch_alter_table(table) as batch:
            for column in restored_columns:
                if column.server_default is not None and column.name != "attempts":
                    batch.alter_column(column.name, server_default=None)
