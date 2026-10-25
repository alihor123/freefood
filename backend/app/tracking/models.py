from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime, utc_now


class TrackingRule(Base):
    """Правило пользователя для товара или категории."""

    __tablename__ = "tracking_rules"
    __table_args__ = (
        CheckConstraint(
            "(product_id IS NOT NULL AND category_id IS NULL) OR "
            "(product_id IS NULL AND category_id IS NOT NULL)",
            name="ck_tracking_rules_one_target",
        ),
        UniqueConstraint("user_id", "product_id", name="uq_tracking_rules_user_product"),
        UniqueConstraint("user_id", "category_id", name="uq_tracking_rules_user_category"),
        Index("ix_tracking_rules_product_active", "product_id", "is_active"),
        Index("ix_tracking_rules_category_active", "category_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT")
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    min_discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now
    )
