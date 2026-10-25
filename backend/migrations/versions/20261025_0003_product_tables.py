"""Создаёт каталог, правила отслеживания и уведомления."""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261025_0003"
down_revision: Union[str, Sequence[str], None] = "20261025_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создаёт справочник каталога, правила и очередь уведомлений."""
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(trim(code)) > 0", name="ck_stores_code_nonempty"
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name="ck_stores_name_nonempty"
        ),
        sa.UniqueConstraint("code", name="uq_stores_code"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(trim(external_id)) > 0",
            name="ck_categories_external_id_nonempty",
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name="ck_categories_name_nonempty"
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "store_id", "external_id", name="uq_categories_store_external"
        ),
        sa.UniqueConstraint("id", "store_id", name="uq_categories_id_store"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("current_price_kopecks", sa.Integer(), nullable=True),
        sa.Column("previous_price_kopecks", sa.Integer(), nullable=True),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("in_stock", sa.Boolean(), nullable=True),
        sa.Column("availability", sa.Text(), nullable=True),
        sa.Column("last_checked", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(trim(external_id)) > 0",
            name="ck_products_external_id_nonempty",
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_products_name_nonempty"),
        sa.CheckConstraint(
            "current_price_kopecks IS NULL OR current_price_kopecks >= 0",
            name="ck_products_current_price_nonnegative",
        ),
        sa.CheckConstraint(
            "previous_price_kopecks IS NULL OR previous_price_kopecks >= 0",
            name="ck_products_previous_price_nonnegative",
        ),
        sa.CheckConstraint(
            "discount_percent IS NULL OR discount_percent BETWEEN 0 AND 100",
            name="ck_products_discount_range",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["category_id", "store_id"],
            ["categories.id", "categories.store_id"],
            ondelete="RESTRICT",
            name="fk_products_category_store",
        ),
        sa.UniqueConstraint(
            "store_id", "external_id", name="uq_products_store_external"
        ),
    )
    op.create_index(
        "ix_products_store_category", "products", ["store_id", "category_id"]
    )
    op.create_table(
        "tracking_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("min_discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(product_id IS NOT NULL AND category_id IS NULL) OR "
            "(product_id IS NULL AND category_id IS NOT NULL)",
            name="ck_tracking_rules_one_target",
        ),
        sa.CheckConstraint(
            "min_discount_percent BETWEEN 0 AND 100",
            name="ck_tracking_rules_discount_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "user_id", "product_id", name="uq_tracking_rules_user_product"
        ),
        sa.UniqueConstraint(
            "user_id", "category_id", name="uq_tracking_rules_user_category"
        ),
    )
    op.create_index(
        "ix_tracking_rules_product_active",
        "tracking_rules",
        ["product_id", "is_active"],
    )
    op.create_index(
        "ix_tracking_rules_category_active",
        "tracking_rules",
        ["category_id", "is_active"],
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("store_name", sa.String(128), nullable=False),
        sa.Column("price_kopecks", sa.Integer(), nullable=True),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("threshold_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "status", sa.String(16), server_default="pending", nullable=False
        ),
        sa.Column(
            "attempts", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "price_kopecks IS NULL OR price_kopecks >= 0",
            name="ck_notifications_price_nonnegative",
        ),
        sa.CheckConstraint(
            "discount_percent BETWEEN 0 AND 100",
            name="ck_notifications_discount_range",
        ),
        sa.CheckConstraint(
            "threshold_percent BETWEEN 0 AND 100",
            name="ck_notifications_threshold_range",
        ),
        sa.CheckConstraint(
            "attempts >= 0", name="ck_notifications_attempts_nonnegative"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'cancelled')",
            name="ck_notifications_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["tracking_rules.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_notifications_user_created", "notifications", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_notifications_status_next_attempt",
        "notifications",
        ["status", "next_attempt_at"],
    )
    op.create_index("ix_notifications_rule_id", "notifications", ["rule_id"])
    op.create_index("ix_notifications_product_id", "notifications", ["product_id"])

    stores = sa.table(
        "stores",
        sa.column("code", sa.String(32)),
        sa.column("name", sa.String(128)),
        sa.column("website_url", sa.Text()),
        sa.column("created_at", sa.DateTime()),
    )
    op.bulk_insert(
        stores,
        [
            {
                "code": "magnit",
                "name": "Магнит",
                "website_url": "https://magnit.ru",
                "created_at": datetime.now(timezone.utc),
            }
        ],
    )


def downgrade() -> None:
    """Удаляет добавленные продуктовые таблицы."""
    op.drop_table("notifications")
    op.drop_index("ix_tracking_rules_category_active", table_name="tracking_rules")
    op.drop_index("ix_tracking_rules_product_active", table_name="tracking_rules")
    op.drop_table("tracking_rules")
    op.drop_index("ix_products_store_category", table_name="products")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("stores")
