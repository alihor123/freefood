import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from authx import RequestToken
from sqlalchemy import delete, func, select, update

from app.config import settings
from app.auth.models import AuthSession, User
from app.auth.tokens import security
from app.database import AsyncSessionLocal
from app.tasks.cleanup import cleanup_old_sessions


def _login(client, init_data: str, device_id: str | None = None) -> dict:
    response = client.post(
        "/api/auth/telegram",
        json={"init_data": init_data},
        headers={"X-Device-Id": device_id or str(uuid4())},
    )
    assert response.status_code == 200
    # Здесь передаём токены явно, поведение cookies проверяется отдельно.
    client.cookies.clear()
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


async def _invalidate_session(session_id: str, state: str) -> None:
    async with AsyncSessionLocal() as db:
        if state == "deleted":
            statement = delete(AuthSession).where(AuthSession.id == session_id)
        else:
            values = (
                {"revoked_at": datetime.now(timezone.utc)}
                if state == "revoked"
                else {"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}
            )
            statement = (
                update(AuthSession).where(AuthSession.id == session_id).values(**values)
            )
        await db.execute(statement)
        await db.commit()


async def _session_ids(user_id: int) -> list[str]:
    async with AsyncSessionLocal() as db:
        result = await db.scalars(
            select(AuthSession.id).where(AuthSession.user_id == user_id)
        )
        return sorted(result.all())


async def _count_users() -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(User))


def test_telegram_profile_keeps_names_without_language_code(client, init_data_factory):
    tokens = _login(client, init_data_factory())
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    profile = response.json()
    assert profile["first_name"] == "Тестовый пользователь"
    assert profile["last_name"] == "Проверка"
    assert profile["username"] == "freefood_test"
    assert profile["created_at"]
    assert "language_code" not in profile


async def _count_sessions() -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(AuthSession))


def test_login_rotation_rejects_old_refresh_and_keeps_one_session(
    client,
    init_data_factory,
):
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

    client.cookies.clear()
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


@pytest.mark.parametrize("state", ["revoked", "expired", "deleted"])
def test_inactive_session_rejects_access_and_refresh(client, init_data_factory, state):
    tokens = _login(client, init_data_factory())
    session_id = _claims(tokens["access_token"], "access")[1]
    client.portal.call(_invalidate_session, session_id, state)

    access_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert access_response.status_code == 401
    assert refresh_response.status_code == 401


def test_different_devices_create_independent_sessions(client, init_data_factory):
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


def test_same_device_login_reuses_session_and_replaces_refresh(client, init_data_factory):
    init_data = init_data_factory()
    device_id = str(uuid4())
    first = _login(client, init_data, device_id)
    second = _login(client, init_data, device_id)
    session_id = _claims(first["access_token"], "access")[1]

    assert _claims(second["access_token"], "access")[1] == session_id
    assert client.portal.call(_session_ids, first["user"]["id"]) == [session_id]
    assert client.post(
        "/api/auth/refresh", json={"refresh_token": first["refresh_token"]}
    ).status_code == 401
    assert client.post(
        "/api/auth/refresh", json={"refresh_token": second["refresh_token"]}
    ).status_code == 200


@pytest.mark.parametrize("state", ["revoked", "expired", "deleted"])
def test_login_creates_new_session_after_previous_one_ended(
    client, init_data_factory, state
):
    init_data = init_data_factory()
    device_id = str(uuid4())
    first = _login(client, init_data, device_id)
    old_id = _claims(first["access_token"], "access")[1]
    client.portal.call(_invalidate_session, old_id, state)
    second = _login(client, init_data, device_id)
    new_id = _claims(second["access_token"], "access")[1]

    assert new_id != old_id
    assert client.portal.call(_session_ids, first["user"]["id"]) == [new_id]
    assert client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {first['access_token']}"},
    ).status_code == 401
    assert client.post(
        "/api/auth/refresh", json={"refresh_token": first["refresh_token"]}
    ).status_code == 401
    assert client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    ).status_code == 200


def test_same_device_can_have_sessions_of_different_users(client, init_data_factory):
    device_id = str(uuid4())
    first = _login(client, init_data_factory(), device_id)
    other = _login(client, init_data_factory(telegram_id=987654321), device_id)
    repeated = _login(client, init_data_factory(), device_id)
    assert _claims(repeated["access_token"], "access")[1] == _claims(
        first["access_token"], "access"
    )[1]
    assert other["user"]["id"] != repeated["user"]["id"]
    assert client.portal.call(_count_sessions) == 2


@pytest.mark.parametrize("existing", [False, True])
def test_concurrent_logins_on_same_device_keep_one_session(
    client, init_data_factory, existing
):
    init_data = init_data_factory()
    device_id = str(uuid4())
    if existing:
        _login(client, init_data, device_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                client.post,
                "/api/auth/telegram",
                json={"init_data": init_data},
                headers={"X-Device-Id": device_id},
            )
            for _ in range(2)
        ]
        responses = [future.result(timeout=15) for future in futures]

    assert [response.status_code for response in responses] == [200, 200]
    tokens = [response.json() for response in responses]
    ids = {_claims(token["access_token"], "access")[1] for token in tokens}
    assert len(ids) == 1
    assert client.portal.call(_count_users) == 1
    assert client.portal.call(_count_sessions) == 1
    session_id = next(iter(ids))
    current_hash = client.portal.call(_session_state, session_id)[0]
    assert sum(
        hashlib.sha256(token["refresh_token"].encode()).hexdigest() == current_hash
        for token in tokens
    ) == 1


def test_concurrent_first_logins_create_one_user_and_two_sessions(
    client,
    init_data_factory,
):
    init_data = init_data_factory()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                client.post,
                "/api/auth/telegram",
                json={"init_data": init_data},
                headers={"X-Device-Id": str(uuid4())},
            )
            for _ in range(2)
        ]
        responses = [future.result(timeout=15) for future in futures]

    assert [response.status_code for response in responses] == [200, 200]
    tokens = [response.json() for response in responses]
    user_id = tokens[0]["user"]["id"]
    session_ids = [_claims(token["access_token"], "access")[1] for token in tokens]

    assert tokens[1]["user"]["id"] == user_id
    assert len(set(session_ids)) == 2
    assert client.portal.call(_count_users) == 1
    assert client.portal.call(_session_ids, user_id) == sorted(session_ids)


def test_new_login_removes_oldest_active_session_only_for_current_user(
    client,
    init_data_factory,
):
    init_data = init_data_factory()
    tokens = [_login(client, init_data) for _ in range(5)]
    other = _login(client, init_data_factory(telegram_id=987654321))
    tokens.append(_login(client, init_data))
    user_id = tokens[-1]["user"]["id"]
    expected_ids = sorted(
        _claims(token["access_token"], "access")[1] for token in tokens[1:]
    )
    assert client.portal.call(_session_ids, user_id) == expected_ids
    assert client.portal.call(_count_sessions) == 6

    oldest = tokens[0]
    assert client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {oldest['access_token']}"},
    ).status_code == 401
    assert client.post(
        "/api/auth/refresh", json={"refresh_token": oldest["refresh_token"]}
    ).status_code == 401
    for valid in (tokens[-1], other):
        assert client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {valid['access_token']}"},
        ).status_code == 200


def test_expired_and_revoked_sessions_do_not_count_toward_limit(
    client,
    init_data_factory,
):
    init_data = init_data_factory()
    first = _login(client, init_data)
    user_id = first["user"]["id"]
    client.portal.call(_add_cleanup_rows, user_id, datetime.now(timezone.utc))
    for _ in range(4):
        _login(client, init_data)

    assert client.portal.call(_count_sessions) == 8
    assert client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {first['access_token']}"},
    ).status_code == 200


def test_concurrent_logins_keep_active_session_limit(client, init_data_factory):
    init_data = init_data_factory()
    first = [_login(client, init_data) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                client.post,
                "/api/auth/telegram",
                json={"init_data": init_data},
                headers={"X-Device-Id": str(uuid4())},
            )
            for _ in range(2)
        ]
        responses = [future.result(timeout=15) for future in futures]

    assert [response.status_code for response in responses] == [200, 200]
    current_ids = client.portal.call(_session_ids, first[0]["user"]["id"])
    assert len(current_ids) == 5
    assert _claims(first[0]["access_token"], "access")[1] not in current_ids
    for response in responses:
        assert _claims(response.json()["access_token"], "access")[1] in current_ids


def test_reusing_device_at_session_limit_keeps_other_sessions(client, init_data_factory):
    init_data = init_data_factory()
    devices = [str(uuid4()) for _ in range(5)]
    tokens = [_login(client, init_data, device) for device in devices]
    before = client.portal.call(_session_ids, tokens[0]["user"]["id"])
    repeated = _login(client, init_data, devices[0])
    assert _claims(repeated["access_token"], "access")[1] == _claims(
        tokens[0]["access_token"], "access"
    )[1]
    assert client.portal.call(_session_ids, repeated["user"]["id"]) == before


@pytest.mark.parametrize("device_id", [None, "not-a-uuid"])
def test_login_requires_valid_device_header(client, init_data_factory, device_id):
    client.headers.pop("X-Device-Id", None)
    headers = {} if device_id is None else {"X-Device-Id": device_id}
    response = client.post(
        "/api/auth/telegram",
        json={"init_data": init_data_factory()},
        headers=headers,
    )
    assert response.status_code == 422
    assert client.portal.call(_count_sessions) == 0


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


def test_me_and_refresh_reject_signed_tokens_with_invalid_claims(
    client,
    init_data_factory,
):
    tokens = _login(client, init_data_factory())
    user_id, session_id = _claims(tokens["access_token"], "access")
    missing_session_access = security.create_access_token(uid=str(user_id), data={})
    malformed_user_refresh = security.create_refresh_token(
        uid="not-a-user-id",
        data={"session_id": session_id},
    )
    huge_user_access = security.create_access_token(
        uid="9" * 128,
        data={"session_id": session_id},
    )
    huge_user_refresh = security.create_refresh_token(
        uid="9" * 128,
        data={"session_id": session_id},
    )

    access_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {missing_session_access}"},
    )
    refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": malformed_user_refresh},
    )
    huge_access_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {huge_user_access}"},
    )
    huge_refresh_response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": huge_user_refresh},
    )

    assert access_response.status_code == 401
    assert refresh_response.status_code == 401
    assert huge_access_response.status_code == 401
    assert huge_refresh_response.status_code == 401


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
                    device_id=str(uuid4()),
                    refresh_token_hash="a" * 64,
                    created_at=now - timedelta(days=1),
                    expires_at=now - timedelta(seconds=1),
                ),
                AuthSession(
                    id=str(uuid4()),
                    user_id=user_id,
                    device_id=str(uuid4()),
                    refresh_token_hash="b" * 64,
                    created_at=now - timedelta(days=1),
                    expires_at=now + timedelta(days=1),
                    revoked_at=now,
                ),
                AuthSession(
                    id=str(uuid4()),
                    user_id=user_id,
                    device_id=str(uuid4()),
                    refresh_token_hash="c" * 64,
                    created_at=now - timedelta(days=1),
                    expires_at=now,
                ),
            ]
        )
        await db.commit()


def test_cleanup_removes_expired_and_revoked_sessions_without_retention(
    client,
    init_data_factory,
):
    tokens = _login(client, init_data_factory())
    user_id = tokens["user"]["id"]
    active_session_id = _claims(tokens["access_token"], "access")[1]
    now = datetime.now(timezone.utc)
    client.portal.call(_add_cleanup_rows, user_id, now)

    deleted = client.portal.call(cleanup_old_sessions)

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
