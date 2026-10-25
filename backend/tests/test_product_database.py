import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.auth.models import AuthSession, Base, User
from app.catalog.models import Category, Product, Store
from app.config import BACKEND_DIR, settings
from app.notifications.models import Notification
from app.tracking.models import TrackingRule


APP_TABLES = {
    "users",
    "auth_sessions",
    "stores",
    "categories",
    "products",
    "tracking_rules",
    "notifications",
}
EXPECTED_DATABASE_TABLES = APP_TABLES | {"alembic_version"}
MODEL_CLASSES = (
    User,
    AuthSession,
    Store,
    Category,
    Product,
    TrackingRule,
    Notification,
)


def _run_migration(monkeypatch, database_path, revision="head"):
    monkeypatch.setattr(settings, "DATABASE_NAME", str(database_path))
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    with patch("logging.config.fileConfig"):
        command.upgrade(config, revision)


def _normalize_sql(value):
    return " ".join(value.split()) if value is not None else None


def _metadata_foreign_keys(table):
    constraints = set()
    for constraint in table.foreign_key_constraints:
        elements = list(constraint.elements)
        constraints.add(
            (
                constraint.name,
                tuple(element.parent.name for element in elements),
                elements[0].column.table.name,
                tuple(element.column.name for element in elements),
                (constraint.ondelete or "NO ACTION").upper(),
            )
        )
    return constraints


def test_fresh_migration_creates_product_tables_and_only_magnit_seed(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "fresh.db"
    _run_migration(monkeypatch, database_path)

    with closing(sqlite3.connect(database_path)) as db:
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert tables == EXPECTED_DATABASE_TABLES
        assert db.execute(
            "SELECT code, name, website_url, logo_url, is_active FROM stores"
        ).fetchall() == [("magnit", "Магнит", "https://magnit.ru", None, 1)]
        assert db.execute("SELECT COUNT(*) FROM categories").fetchone() == (0,)
        assert db.execute("SELECT COUNT(*) FROM products").fetchone() == (0,)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_product_migration_matches_sqlalchemy_table_metadata(tmp_path, monkeypatch):
    database_path = tmp_path / "metadata.db"
    _run_migration(monkeypatch, database_path)
    assert {model.__tablename__ for model in MODEL_CLASSES} == APP_TABLES

    with create_engine(f"sqlite:///{database_path}").connect() as connection:
        inspector = inspect(connection)
        assert set(inspector.get_table_names()) == EXPECTED_DATABASE_TABLES

        for table_name in APP_TABLES:
            metadata_table = Base.metadata.tables[table_name]
            actual_columns = {
                column["name"]: column for column in inspector.get_columns(table_name)
            }
            assert set(actual_columns) == set(metadata_table.columns.keys())

            for column in metadata_table.columns:
                actual = actual_columns[column.name]
                assert actual["nullable"] == column.nullable
                assert actual["type"].compile(
                    dialect=connection.dialect
                ) == column.type.compile(dialect=connection.dialect)
                expected_default = (
                    str(column.server_default.arg.compile(dialect=connection.dialect))
                    if column.server_default is not None
                    else None
                )
                assert _normalize_sql(actual["default"]) == _normalize_sql(
                    expected_default
                )

            metadata_indexes = {
                (
                    index.name,
                    tuple(column.name for column in index.columns),
                    index.unique,
                )
                for index in metadata_table.indexes
            }
            actual_indexes = {
                (
                    index["name"],
                    tuple(index["column_names"]),
                    index["unique"],
                )
                for index in inspector.get_indexes(table_name)
            }
            assert actual_indexes == metadata_indexes

            metadata_uniques = {
                (constraint.name, tuple(column.name for column in constraint.columns))
                for constraint in metadata_table.constraints
                if constraint.__class__.__name__ == "UniqueConstraint"
            }
            actual_uniques = {
                (constraint["name"], tuple(constraint["column_names"]))
                for constraint in inspector.get_unique_constraints(table_name)
            }
            assert actual_uniques == metadata_uniques

            metadata_checks = {
                (constraint.name, _normalize_sql(str(constraint.sqltext)))
                for constraint in metadata_table.constraints
                if constraint.__class__.__name__ == "CheckConstraint"
            }
            actual_checks = {
                (constraint["name"], _normalize_sql(constraint["sqltext"]))
                for constraint in inspector.get_check_constraints(table_name)
            }
            assert actual_checks == metadata_checks

            metadata_primary_key = tuple(
                column.name for column in metadata_table.primary_key.columns
            )
            actual_primary_key = tuple(
                inspector.get_pk_constraint(table_name)["constrained_columns"]
            )
            assert actual_primary_key == metadata_primary_key

            metadata_foreign_keys = _metadata_foreign_keys(metadata_table)
            actual_foreign_keys = {
                (
                    foreign_key["name"],
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                    (
                        foreign_key.get("options", {}).get("ondelete") or "NO ACTION"
                    ).upper(),
                )
                for foreign_key in inspector.get_foreign_keys(table_name)
            }
            assert actual_foreign_keys == metadata_foreign_keys


def test_product_migration_preserves_auth_rows_created_at_auth_only_revision(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "existing-auth.db"
    session_id = str(uuid4())
    created_at = datetime(2026, 10, 25, tzinfo=timezone.utc).isoformat()
    expires_at = datetime(2026, 11, 1, tzinfo=timezone.utc).isoformat()
    _run_migration(monkeypatch, database_path, "20261025_0002")

    with closing(sqlite3.connect(database_path)) as db, db:
        db.execute(
            "INSERT INTO users "
            "(id, telegram_id, first_name, created_at) "
            "VALUES (1, 123456789, 'Тестовый пользователь', ?)",
            (created_at,),
        )
        db.execute(
            "INSERT INTO auth_sessions "
            "(id, user_id, device_id, refresh_token_hash, created_at, expires_at) "
            "VALUES (?, 1, ?, ?, ?, ?)",
            (session_id, str(uuid4()), "a" * 64, created_at, expires_at),
        )
        user_before = db.execute(
            "SELECT id, telegram_id, username, first_name, last_name, created_at FROM users WHERE id = 1"
        ).fetchone()
        session_before = db.execute(
            "SELECT * FROM auth_sessions WHERE id = ?", (session_id,)
        ).fetchone()

    _run_migration(monkeypatch, database_path)

    with closing(sqlite3.connect(database_path)) as db:
        assert (
            db.execute(
                "SELECT id, telegram_id, username, first_name, last_name, created_at FROM users WHERE id = 1"
            ).fetchone()
            == user_before
        )
        assert (
            db.execute(
                "SELECT * FROM auth_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            == session_before
        )
        assert db.execute("SELECT code FROM stores").fetchall() == [("magnit",)]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_database_constraints_protect_targets_scope_and_notification_history(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "constraints.db"
    _run_migration(monkeypatch, database_path)
    timestamp = "2026-10-25 00:00:00"

    with closing(sqlite3.connect(database_path)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        store_id = db.execute("SELECT id FROM stores WHERE code = 'magnit'").fetchone()[
            0
        ]
        other_store_id = db.execute(
            "INSERT INTO stores (code, name) VALUES (?, ?)",
            ("other", "Другой магазин"),
        ).lastrowid
        category_id = db.execute(
            "INSERT INTO categories (store_id, external_id, name) VALUES (?, ?, ?)",
            (store_id, "cat-1", "Категория"),
        ).lastrowid
        db.execute(
            "INSERT INTO categories (store_id, external_id, name) VALUES (?, ?, ?)",
            (other_store_id, "cat-2", "Другая категория"),
        )
        db.execute(
            "INSERT INTO users (id, telegram_id, first_name, created_at) "
            "VALUES (1, 123456789, 'Тестовый пользователь', ?)",
            (timestamp,),
        )
        product_id = db.execute(
            "INSERT INTO products "
            "(store_id, category_id, external_id, name, current_price_kopecks, "
            "discount_percent) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (store_id, category_id, "prod-1", "Товар", 1999, 20),
        ).lastrowid

        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            db.execute(
                "INSERT INTO products "
                "(store_id, category_id, external_id, name) "
                "VALUES (?, ?, ?, ?)",
                (
                    other_store_id,
                    category_id,
                    "cross-store",
                    "Чужая категория",
                ),
            )

        rule_id = db.execute(
            "INSERT INTO tracking_rules "
            "(user_id, product_id, min_discount_percent, created_at) "
            "VALUES (?, ?, ?, ?)",
            (1, product_id, 15, timestamp),
        ).lastrowid
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            db.execute(
                "INSERT INTO tracking_rules "
                "(user_id, product_id, min_discount_percent, created_at) "
                "VALUES (?, ?, ?, ?)",
                (1, product_id, 25, timestamp),
            )

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            db.execute(
                "INSERT INTO tracking_rules "
                "(user_id, min_discount_percent, created_at) "
                "VALUES (?, ?, ?)",
                (1, 10, timestamp),
            )

        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            db.execute(
                "INSERT INTO tracking_rules "
                "(user_id, product_id, category_id, min_discount_percent, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (1, product_id, category_id, 10, timestamp),
            )

        notification_id = db.execute(
            "INSERT INTO notifications "
            "(user_id, rule_id, product_id, product_name, store_name, price_kopecks, "
            "discount_percent, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                rule_id,
                product_id,
                "Товар в истории",
                "Магнит",
                1999,
                20,
                timestamp,
            ),
        ).lastrowid

        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            db.execute("DELETE FROM products WHERE id = ?", (product_id,))

        db.execute("DELETE FROM tracking_rules WHERE id = ?", (rule_id,))
        assert db.execute(
            "SELECT rule_id, product_id FROM notifications WHERE id = ?",
            (notification_id,),
        ).fetchone() == (None, product_id)

        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        assert db.execute(
            "SELECT rule_id, product_id, product_name, store_name, price_kopecks, "
            "discount_percent FROM notifications WHERE id = ?",
            (notification_id,),
        ).fetchone() == (None, None, "Товар в истории", "Магнит", 1999, 20)


def test_validation_migration_preserves_catalog_rules_and_notifications(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "validation-migration.db"
    _run_migration(monkeypatch, database_path, "20261025_0003")
    timestamp = "2026-10-25 00:00:00"

    with closing(sqlite3.connect(database_path)) as db, db:
        store_id = db.execute("SELECT id FROM stores").fetchone()[0]
        db.execute(
            "INSERT INTO users (id, telegram_id, first_name, created_at) "
            "VALUES (1, 123456789, 'Тест', ?)",
            (timestamp,),
        )
        db.execute(
            "INSERT INTO categories "
            "(id, store_id, external_id, name, created_at, updated_at) "
            "VALUES (1, ?, 'cat-1', 'Категория', ?, ?)",
            (store_id, timestamp, timestamp),
        )
        db.execute(
            "INSERT INTO products "
            "(id, store_id, category_id, external_id, name, current_price_kopecks, "
            "discount_percent, created_at, updated_at) "
            "VALUES (1, ?, 1, 'prod-1', 'Товар', 1999, 30, ?, ?)",
            (store_id, timestamp, timestamp),
        )
        db.execute(
            "INSERT INTO tracking_rules "
            "(id, user_id, product_id, min_discount_percent, created_at, updated_at) "
            "VALUES (1, 1, 1, 20, ?, ?)",
            (timestamp, timestamp),
        )
        db.execute(
            "INSERT INTO notifications "
            "(user_id, rule_id, product_id, product_name, store_name, price_kopecks, "
            "discount_percent, threshold_percent, created_at) "
            "VALUES (1, 1, 1, 'Товар', 'Магнит', 1999, 30, 20, ?)",
            (timestamp,),
        )
        before = {
            table: db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            for table in APP_TABLES
        }

    for revision in ("20261025_0004", "20261025_0003", "20261025_0004"):
        if revision == "20261025_0004":
            _run_migration(monkeypatch, database_path, revision)
        else:
            with patch("logging.config.fileConfig"):
                command.downgrade(Config(str(BACKEND_DIR / "alembic.ini")), revision)
        with closing(sqlite3.connect(database_path)) as db:
            after = {
                table: db.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
                for table in APP_TABLES
            }
            assert after == before
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_simplification_preserves_remaining_data_on_upgrade_and_downgrade(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "simplification.db"
    _run_migration(monkeypatch, database_path, "20261025_0004")
    timestamp = "2026-10-24 12:34:56"
    session_id = str(uuid4())
    rows = {
        "users": {
            "id": 1,
            "telegram_id": 123456789,
            "username": "tester",
            "first_name": "Егор",
            "last_name": "Тестов",
            "language_code": "ru",
            "created_at": timestamp,
        },
        "auth_sessions": {
            "id": session_id,
            "user_id": 1,
            "device_id": str(uuid4()),
            "refresh_token_hash": "a" * 64,
            "created_at": timestamp,
            "expires_at": "2026-11-01 00:00:00",
            "revoked_at": None,
        },
        "categories": {
            "id": 1,
            "store_id": 1,
            "external_id": "cat-100",
            "name": "Шоколад",
            "created_at": timestamp,
            "updated_at": timestamp,
        },
        "products": {
            "id": 1,
            "store_id": 1,
            "category_id": 1,
            "external_id": "prod-100",
            "name": "Шоколад",
            "description": "Тёмный шоколад",
            "image_url": "https://example.com/product.png",
            "source_url": "https://example.com/product",
            "current_price_kopecks": 1999,
            "previous_price_kopecks": 2999,
            "discount_percent": 33.34,
            "in_stock": 1,
            "availability": "Есть в наличии",
            "last_checked": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
        "tracking_rules": {
            "id": 1,
            "user_id": 1,
            "product_id": 1,
            "category_id": None,
            "min_discount_percent": 30,
            "is_active": 1,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
        "notifications": {
            "id": 1,
            "user_id": 1,
            "rule_id": 1,
            "product_id": 1,
            "product_name": "Шоколад на момент события",
            "store_name": "Магнит",
            "price_kopecks": 1999,
            "discount_percent": 33.34,
            "threshold_percent": 30,
            "status": "pending",
            "attempts": 2,
            "created_at": timestamp,
            "sent_at": None,
            "next_attempt_at": "2026-10-24 13:00:00",
            "last_error": "Таймаут",
        },
    }
    with closing(sqlite3.connect(database_path)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute(
            "UPDATE stores SET website_url = ?, logo_url = ?, is_active = 0",
            ("https://example.com", "https://example.com/logo.png"),
        )
        for table, values in rows.items():
            columns = ", ".join(values)
            parameters = ", ".join("?" for _ in values)
            db.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({parameters})",
                tuple(values.values()),
            )
        remaining = {
            name: ", ".join(Base.metadata.tables[name].columns.keys())
            for name in APP_TABLES
        }
        before = {
            name: db.execute(f"SELECT {columns} FROM {name} ORDER BY id").fetchall()
            for name, columns in remaining.items()
        }

    _run_migration(monkeypatch, database_path)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    for revision in ("head", "20261025_0004", "head"):
        with patch("logging.config.fileConfig"):
            if revision == "head":
                command.upgrade(config, revision)
                command.check(config)
            else:
                command.downgrade(config, revision)
        with closing(sqlite3.connect(database_path)) as db:
            after = {
                name: db.execute(f"SELECT {columns} FROM {name} ORDER BY id").fetchall()
                for name, columns in remaining.items()
            }
            assert after == before
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
