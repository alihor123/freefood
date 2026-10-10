import hmac
from http.cookies import SimpleCookie

import pytest

from app.config import settings
from app.services.token_service import security


def _login(client, init_data: str):
    response = client.post("/api/auth/telegram", json={"init_data": init_data})
    assert response.status_code == 200
    return response


def _cookie_morsel(response, name: str):
    for header in response.headers.get_list("set-cookie"):
        if header.partition("=")[0] == name:
            cookies = SimpleCookie()
            cookies.load(header)
            return cookies.get(name)
    return None


def _cookie_has_flag(response, name: str, flag: str) -> bool:
    cookie = _cookie_morsel(response, name)
    return cookie is not None and bool(cookie[flag])


def _cookie_attribute_is(response, name: str, attribute: str, expected: str) -> bool:
    cookie = _cookie_morsel(response, name)
    return cookie is not None and cookie[attribute].lower() == expected.lower()


def _response_cookie_matches(response, name: str, token: str) -> bool:
    cookie = _cookie_morsel(response, name)
    return cookie is not None and hmac.compare_digest(cookie.value, token)


def _response_cookie_is_empty(response, name: str) -> bool:
    cookie = _cookie_morsel(response, name)
    return cookie is not None and cookie.value == ""


def _same_token(first: str, second: str) -> bool:
    return hmac.compare_digest(first, second)


def test_login_returns_json_pair_and_sets_authx_cookies(client, init_data_factory):
    response = _login(client, init_data_factory())
    tokens = response.json()
    access_max_age = str(settings.JWT_ACCESS_TTL_MINUTES * 60)
    refresh_max_age = str(settings.JWT_REFRESH_TTL_DAYS * 24 * 60 * 60)
    same_site = security.config.JWT_COOKIE_SAMESITE

    for cookie_name, token_field, max_age in (
        ("access_token_cookie", "access_token", access_max_age),
        ("refresh_token_cookie", "refresh_token", refresh_max_age),
    ):
        assert _response_cookie_matches(response, cookie_name, tokens[token_field]), (
            "auth cookie must match the JSON token"
        )
        assert _cookie_has_flag(response, cookie_name, "httponly"), (
            "auth cookie must be HttpOnly"
        )
        assert _cookie_attribute_is(response, cookie_name, "path", "/"), (
            "auth cookie path must be root"
        )
        assert _cookie_attribute_is(response, cookie_name, "samesite", same_site), (
            "auth cookie SameSite must follow AuthX config"
        )
        assert _cookie_attribute_is(response, cookie_name, "max-age", max_age), (
            "auth cookie Max-Age must match its token lifetime"
        )

    for cookie_name, max_age in (
        ("csrf_access_token", access_max_age),
        ("csrf_refresh_token", refresh_max_age),
    ):
        assert not _cookie_has_flag(response, cookie_name, "httponly"), (
            "double-submit CSRF cookie must be readable by the client"
        )
        assert _cookie_attribute_is(response, cookie_name, "path", "/")
        assert _cookie_attribute_is(response, cookie_name, "samesite", same_site)
        assert _cookie_attribute_is(response, cookie_name, "max-age", max_age)


def test_me_accepts_access_cookie(client, init_data_factory):
    login = _login(client, init_data_factory())

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["id"] == login.json()["user"]["id"]


def test_cookie_refresh_requires_csrf_and_rotates_pair(client, init_data_factory):
    login = _login(client, init_data_factory())
    old_tokens = login.json()

    assert client.post("/api/auth/refresh").status_code == 401
    assert (
        client.post(
            "/api/auth/refresh",
            headers={"X-CSRF-TOKEN": "invalid"},
        ).status_code
        == 401
    )

    csrf_token = client.cookies.get("csrf_refresh_token")
    assert csrf_token
    response = client.post(
        "/api/auth/refresh",
        headers={"X-CSRF-TOKEN": csrf_token},
    )

    assert response.status_code == 200
    new_tokens = response.json()
    assert _response_cookie_matches(
        response, "access_token_cookie", new_tokens["access_token"]
    ), "access cookie must match the rotated JSON token"
    assert _response_cookie_matches(
        response, "refresh_token_cookie", new_tokens["refresh_token"]
    ), "refresh cookie must match the rotated JSON token"
    assert not _same_token(old_tokens["access_token"], new_tokens["access_token"])
    assert not _same_token(old_tokens["refresh_token"], new_tokens["refresh_token"])

    replay = client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_tokens["refresh_token"]},
    )
    assert replay.status_code == 401


def test_cookie_logout_requires_csrf_revokes_session_and_deletes_cookies(
    client,
    init_data_factory,
):
    login = _login(client, init_data_factory())
    access_token = login.json()["access_token"]

    assert client.post("/api/auth/logout").status_code == 401
    assert (
        client.post(
            "/api/auth/logout",
            headers={"X-CSRF-TOKEN": "invalid"},
        ).status_code
        == 401
    )

    csrf_token = client.cookies.get("csrf_access_token")
    assert csrf_token
    response = client.post(
        "/api/auth/logout",
        headers={"X-CSRF-TOKEN": csrf_token},
    )

    assert response.status_code == 200
    for cookie_name in (
        "access_token_cookie",
        "refresh_token_cookie",
        "csrf_access_token",
        "csrf_refresh_token",
    ):
        assert _response_cookie_is_empty(response, cookie_name), (
            "logout must clear every auth and CSRF cookie"
        )
        assert _cookie_attribute_is(response, cookie_name, "max-age", "0"), (
            "logout must expire every auth and CSRF cookie"
        )

    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        ).status_code
        == 401
    )


def test_mobile_json_refresh_and_bearer_take_priority_over_cookies(
    client,
    init_data_factory,
):
    first_login = _login(client, init_data_factory())
    first_tokens = first_login.json()
    second_login = _login(
        client,
        init_data_factory(telegram_id=987654321),
    )

    invalid_bearer = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid"},
    )
    assert invalid_bearer.status_code == 401

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {first_tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == first_login.json()["user"]["id"]
    assert me.json()["id"] != second_login.json()["user"]["id"]

    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": first_tokens["refresh_token"]},
    )

    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["user"]["id"] == first_login.json()["user"]["id"]
    assert _response_cookie_matches(
        response, "access_token_cookie", new_tokens["access_token"]
    ), "mobile refresh must also update the access cookie"
    assert _response_cookie_matches(
        response, "refresh_token_cookie", new_tokens["refresh_token"]
    ), "mobile refresh must also update the refresh cookie"


@pytest.mark.parametrize(
    ("secure", "same_site"),
    [(False, "lax"), (True, "lax"), (True, "none")],
)
def test_auth_cookie_secure_flag_follows_authx_config(
    client,
    init_data_factory,
    monkeypatch,
    secure,
    same_site,
):
    monkeypatch.setattr(security.config, "JWT_COOKIE_SECURE", secure)
    monkeypatch.setattr(security.config, "JWT_COOKIE_SAMESITE", same_site)

    response = _login(client, init_data_factory())

    for cookie_name in ("access_token_cookie", "refresh_token_cookie"):
        assert _cookie_has_flag(response, cookie_name, "secure") is secure
        assert _cookie_attribute_is(response, cookie_name, "samesite", same_site)


def test_cors_preflight_allows_csrf_header_with_credentials(client):
    origin = "http://127.0.0.1:5173"
    response = client.options(
        "/api/auth/refresh",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-CSRF-TOKEN, Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert response.headers.get("access-control-allow-credentials") == "true"
    allowed_headers = {
        header.strip().lower()
        for header in response.headers.get("access-control-allow-headers", "").split(
            ","
        )
    }
    assert {"x-csrf-token", "content-type"} <= allowed_headers
