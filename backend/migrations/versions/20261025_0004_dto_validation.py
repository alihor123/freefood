"""Переносит проверки отдельных значений в DTO."""

from alembic import op


revision = "20261025_0004"
down_revision = "20261025_0003"
branch_labels = None
depends_on = None


REMOVED_CHECKS = {
    "stores": [
        ("ck_stores_code_nonempty", "length(trim(code)) > 0"),
        ("ck_stores_name_nonempty", "length(trim(name)) > 0"),
    ],
    "categories": [
        ("ck_categories_external_id_nonempty", "length(trim(external_id)) > 0"),
        ("ck_categories_name_nonempty", "length(trim(name)) > 0"),
    ],
    "products": [
        ("ck_products_external_id_nonempty", "length(trim(external_id)) > 0"),
        ("ck_products_name_nonempty", "length(trim(name)) > 0"),
        (
            "ck_products_current_price_nonnegative",
            "current_price_kopecks IS NULL OR current_price_kopecks >= 0",
        ),
        (
            "ck_products_previous_price_nonnegative",
            "previous_price_kopecks IS NULL OR previous_price_kopecks >= 0",
        ),
        (
            "ck_products_discount_range",
            "discount_percent IS NULL OR discount_percent BETWEEN 0 AND 100",
        ),
    ],
    "tracking_rules": [
        ("ck_tracking_rules_discount_range", "min_discount_percent BETWEEN 0 AND 100")
    ],
    "notifications": [
        (
            "ck_notifications_price_nonnegative",
            "price_kopecks IS NULL OR price_kopecks >= 0",
        ),
        ("ck_notifications_discount_range", "discount_percent BETWEEN 0 AND 100"),
        ("ck_notifications_threshold_range", "threshold_percent BETWEEN 0 AND 100"),
        ("ck_notifications_attempts_nonnegative", "attempts >= 0"),
        (
            "ck_notifications_status",
            "status IN ('pending', 'sent', 'failed', 'cancelled')",
        ),
    ],
}


def upgrade() -> None:
    """Убирает проверки полей, сохраняя связи и уникальность."""
    for table, constraints in REMOVED_CHECKS.items():
        with op.batch_alter_table(table) as batch:
            for name, _ in constraints:
                batch.drop_constraint(name, type_="check")


def downgrade() -> None:
    """Восстанавливает ограничения предыдущей схемы."""
    for table, constraints in REMOVED_CHECKS.items():
        with op.batch_alter_table(table) as batch:
            for name, condition in constraints:
                batch.create_check_constraint(name, condition)
