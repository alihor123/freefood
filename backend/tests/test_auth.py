import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from authx import RequestToken
from sqlalchemy import func, select

from app.config import settings
from app.database.database import AsyncSessionLocal
from app.database.models import AuthSession, User
from app.database.repositories.session_repo import cleanup_sessions
from app.services.token_service import security
from app.tasks.cleanup import cleanup_old_sessions


def _login(client, init_data: str) -> dict:
    response = client.post("/api/auth/telegram", json={"init_data": init_data})
    assert response.status_code == 200
    return response.json()


def _claims(token: str, token_type: str) -> tuple[int, str]:
    location = "headers" if token_type == "access" else "json"
    payload = security.verify_token(
        RequestToken(token=token, type=token_type, location=location)
    )
    return int(payload.sub), str(payload.session_id)


def _expiry(token: str, token_type: str) -> datetime:
    location = "headers" if token_type == "access" else "json"
    payload = security.verify_token(
        RequestToken(token=token, type=token_type, location=location)
    )
    return payload.expiry_datetime


def _tamper_signature(token: str) -> str:
    header, payload, signature = token.split(".")
    first = "A" if signature[0] != "A" else "B"
    return f"{header}.{payload}.{first}{signature[1:]}"


async def _session_state(session_id: str):
    async with AsyncSessionLocal() as db:
        session = await db.get(AuthSession, session_id)
        if session is None:
            return None
        return (
            session.refresh_token_hash,
            session.expires_at,
            session.revoked_at,
        )


async def _session_ids(user_id: int) -> list[str]:
    async with AsyncSessionLocal() as db:
        result = await db.scalars(
            select(AuthSession.id).where(AuthSession.user_id == user_id)
        )
        return sorted(result.all())


async def _count_users() -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(User))


async def _count_sessions() -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(AuthSession))


def test_login_rotation_and_logout_keep_one_session(client, init_data_factory):
    init_data = init_data_factory(extra={"signature": "signed-extra-field"})
    first = _login(client, init_data)
    user_id = first["user"]["id"]
    session_id = _claims(first["access_token"], "access")[1]

    assert first["token_type"] == "bearer"
    assert first["expires_in"] > 0
    assert first["user"]["telegram_id"] == 123456789
    initial_state = client.portal.call(_session_state, session_id)
    assert initial_state is not None
    assert initial_state[1].replace(tzinfo=timezone.utc) == _expiry(
        first["refresh_token"], "refresh"
    )
    assert (
        initial_state[0] == hashlib.sha256(first["refresh_token"].encode()).hexdigest()
    )

    rotated_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert rotated_response.status_code == 200
    rotated = rotated_response.json()
    assert rotated["user"]["id"] == user_id
    assert _claims(rotated["access_token"], "access")[1] == session_id
    assert _claims(rotated["refresh_token"], "refresh")[1] == session_id

    rotated_state = client.portal.call(_session_state, session_id)
    assert rotated_state is not None
    assert rotated_state[1].replace(tzinfo=timezone.utc) == _expiry(
        rotated["refresh_token"], "refresh"
    )
    assert (
        rotated_state[0]
        == hashlib.sha256(rotated["refresh_token"].encode()).hexdigest()
    )
    assert rotated_state[0] != initial_state[0]

    replay = client.post(
        "/api/auth/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert replay.status_code == 401
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {first['access_token']}"},
        ).status_code
        == 200
    )

    logout = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {rotated['access_token']}"},
    )
    assert logout.status_code == 200
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {first['access_token']}"},
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {rotated['access_token']}"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/refresh",
            json={"refresh_token": rotated["refresh_token"]},
        ).status_code
        == 401
    )


def test_repeated_login_creates_independent_sessions(client, init_data_factory):
    init_data = init_data_factory()
    first = _login(client, init_data)
    second = _login(client, init_data)

    first_session_id = _claims(first["access_token"], "access")[1]
    second_session_id = _claims(second["access_token"], "access")[1]
    assert first["user"]["id"] == second["user"]["id"]
    assert first_session_id != second_session_id
    assert client.portal.call(_session_ids, first["user"]["id"]) == sorted(
        [first_session_id, second_session_id]
    )


def test_me_and_refresh_reject_missing_tampered_and_wrong_token_types(
    client,
    init_data_factory,
):
    tokens = _login(client, init_data_factory())
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.get(
            "/api/auth/me",
            headers={
                "Authorization": f"Bearer {_tamper_signature(tokens['access_token'])}"
            },
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens["access_token"]},
        ).status_code
        == 401
    )


def test_expired_access_is_rejected_but_refresh_still_works(client, init_data_factory):
    tokens = _login(client, init_data_factory())
    user_id, session_id = _claims(tokens["access_token"], "access")
    expired_access = security.create_access_token(
        uid=str(user_id),
        data={"session_id": session_id},
        expiry=timedelta(seconds=-1),
    )

    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_access}"},
        ).status_code
        == 401
    )
    refreshed = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200


def test_expired_refresh_does_not_change_session(client, init_data_factory):
    tokens = _login(client, init_data_factory())
    user_id, session_id = _claims(tokens["refresh_token"], "refresh")
    expired_refresh = security.create_refresh_token(
        uid=str(user_id),
        data={"session_id": session_id},
        expiry=timedelta(seconds=-1),
    )
    before = client.portal.call(_session_state, session_id)

    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": expired_refresh},
    )
    after = client.portal.call(_session_state, session_id)
    assert response.status_code == 401
    assert after == before


@pytest.mark.parametrize(
    "invalid_kind",
    ["bad_signature", "stale", "future", "duplicate", "malformed_user"],
)
def test_telegram_login_rejects_invalid_init_data(
    client,
    init_data_factory,
    invalid_kind: str,
):
    now = int(time.time())
    if invalid_kind == "bad_signature":
        init_data = init_data_factory()
        hash_start = init_data.index("hash=") + len("hash=")
        old_hash = init_data[hash_start : hash_start + 64]
        replacement = "0" if old_hash[0] != "0" else "1"
        init_data = f"{init_data[:hash_start]}{replacement}{old_hash[1:]}"
    elif invalid_kind == "stale":
        init_data = init_data_factory(auth_date=now - 301)
    elif invalid_kind == "future":
        init_data = init_data_factory(auth_date=now + 90)
    elif invalid_kind == "duplicate":
        init_data = f"{init_data_factory(auth_date=now)}&auth_date={now}"
    else:
        init_data = init_data_factory(
            user={"id": "123456789", "first_name": "Malformed"}
        )

    response = client.post("/api/auth/telegram", json={"init_data": init_data})
    assert response.status_code == 401
    assert client.portal.call(_count_users) == 0


def test_disabling_age_check_still_requires_valid_signed_data(
    client,
    init_data_factory,
    monkeypatch,
):
    monkeypatch.setattr(settings, "TELEGRAM_CHECK_INIT_DATA_AGE", False)

    old_but_signed = client.post(
        "/api/auth/telegram",
        json={"init_data": init_data_factory(auth_date=1)},
    )
    assert old_but_signed.status_code == 200

    malformed_date = client.post(
        "/api/auth/telegram",
        json={"init_data": init_data_factory(auth_date="not-a-date")},
    )
    assert malformed_date.status_code == 401

    bad_signature = init_data_factory(auth_date=1)
    hash_start = bad_signature.index("hash=") + len("hash=")
    old_hash = bad_signature[hash_start : hash_start + 64]
    replacement = "0" if old_hash[0] != "0" else "1"
    bad_signature = f"{bad_signature[:hash_start]}{replacement}{old_hash[1:]}"
    rejected = client.post(
        "/api/auth/telegram",
        json={"init_data": bad_signature},
    )
    assert rejected.status_code == 401


def test_concurrent_refresh_has_one_winner(client, init_data_factory):
    tokens = _login(client, init_data_factory())

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                client.post,
                "/api/auth/refresh",
                json={"refresh_token": tokens["refresh_token"]},
            )
            for _ in range(2)
        ]
        responses = [future.result(timeout=15) for future in futures]

    assert sorted(response.status_code for response in responses) == [200, 401]
    winner = next(
        response.json() for response in responses if response.status_code == 200
    )
    session_id = _claims(tokens["refresh_token"], "refresh")[1]
    state = client.portal.call(_session_state, session_id)
    assert state is not None
    assert state[0] == hashlib.sha256(winner["refresh_token"].encode()).hexdigest()
    assert client.portal.call(_count_sessions) == 1


async def _add_cleanup_rows(user_id: int, now: datetime) -> None:
    async with AsyncSessionLocal() as db:
        db.add_all(
            [
                AuthSession(
                    id=str(uuid4()),
                    user_id=user_id,
                    refresh_token_hash="a" * 64,
                    created_at=now - timedelta(days=1),
                    expires_at=now - timedelta(seconds=1),
                ),
                AuthSession(
                    id=str(uuid4()),
                    user_id=user_id,
                    refresh_token_hash="b" * 64,
                    created_at=now - timedelta(days=1),
                    expires_at=now + timedelta(days=1),
                    revoked_at=now,
                ),
                AuthSession(
                    id=str(uuid4()),
                    user_id=user_id,
                    refresh_token_hash="c" * 64,
                    created_at=now - timedelta(days=1),
                    expires_at=now,
                ),
            ]
        )
        await db.commit()


async def _run_cleanup(now: datetime) -> int:
    async with AsyncSessionLocal() as db:
        return await cleanup_sessions(db, now)


@pytest.mark.parametrize("run_job", [False, True])
def test_cleanup_removes_expired_and_revoked_sessions_without_retention(
    client,
    init_data_factory,
    run_job: bool,
):
    tokens = _login(client, init_data_factory())
    user_id = tokens["user"]["id"]
    active_session_id = _claims(tokens["access_token"], "access")[1]
    now = datetime.now(timezone.utc)
    client.portal.call(_add_cleanup_rows, user_id, now)

    if run_job:
        deleted = client.portal.call(cleanup_old_sessions)
    else:
        deleted = client.portal.call(_run_cleanup, now)

    assert deleted == 3
    assert client.portal.call(_session_ids, user_id) == [active_session_id]
    assert client.portal.call(_count_users) == 1
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        ).status_code
        == 200
    )
