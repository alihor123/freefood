import sqlite3
from contextlib import closing
from unittest.mock import patch
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config

from app.config import BACKEND_DIR, settings


def test_device_migration_preserves_existing_data_and_matches_models(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "existing.db"
    monkeypatch.setattr(settings, "DATABASE_NAME", str(database_path))
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    session_id = str(uuid4())
    with patch("logging.config.fileConfig"):
        command.upgrade(config, "20261010_0001")
        with closing(sqlite3.connect(database_path)) as db, db:
            db.execute(
                "INSERT INTO users (id, telegram_id, first_name, created_at) "
                "VALUES (1, 123, 'Test', '2026-10-25 00:00:00')"
            )
            db.execute(
                "INSERT INTO auth_sessions "
                "(id, user_id, refresh_token_hash, created_at, expires_at) "
                "VALUES (?, 1, ?, '2026-10-25 00:00:00', '2026-11-01 00:00:00')",
                (session_id, "a" * 64),
            )
            before = db.execute("SELECT * FROM auth_sessions").fetchone()

        command.upgrade(config, "head")
        command.upgrade(config, "head")
        command.check(config)
        with closing(sqlite3.connect(database_path)) as db, db:
            after = db.execute("SELECT * FROM auth_sessions").fetchone()
            assert after[:-1] == before
            assert after[-1] == session_id
            columns = db.execute("PRAGMA table_info(auth_sessions)").fetchall()
            assert next(column for column in columns if column[1] == "device_id")[3] == 1
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
                db.execute(
                    "INSERT INTO auth_sessions "
                    "(id, user_id, device_id, refresh_token_hash, created_at, expires_at) "
                    "VALUES (?, 1, ?, ?, '2026-10-25 00:00:00', '2026-11-01 00:00:00')",
                    (str(uuid4()), session_id, "b" * 64),
                )

        command.downgrade(config, "20261010_0001")
        with closing(sqlite3.connect(database_path)) as db:
            assert db.execute("SELECT * FROM auth_sessions").fetchone() == before
        command.upgrade(config, "head")
