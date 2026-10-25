from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class Store(Base):
    """Сеть магазинов, доступная в каталоге."""

    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("code", name="uq_stores_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    website_url: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )


class Category(Base):
    """Категория товаров конкретного магазина."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint(
            "store_id", "external_id", name="uq_categories_store_external"
        ),
        UniqueConstraint("id", "store_id", name="uq_categories_id_store"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class Product(Base):
    """Товар магазина с последним известным состоянием цены и наличия."""

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("store_id", "external_id", name="uq_products_store_external"),
        ForeignKeyConstraint(
            ["category_id", "store_id"],
            ["categories.id", "categories.store_id"],
            ondelete="RESTRICT",
            name="fk_products_category_store",
        ),
        Index("ix_products_store_category", "store_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )
    category_id: Mapped[int | None] = mapped_column(Integer)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    current_price_kopecks: Mapped[int | None] = mapped_column(Integer)
    previous_price_kopecks: Mapped[int | None] = mapped_column(Integer)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    in_stock: Mapped[bool | None] = mapped_column(Boolean)
    last_checked: Mapped[datetime | None] = mapped_column(UTCDateTime())
