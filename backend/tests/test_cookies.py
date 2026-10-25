import hmac
from http.cookies import SimpleCookie

import pytest

from app.config import settings
from app.auth.tokens import security


def _login(client, init_data: str):
    response = client.post("/api/auth/telegram", json={"init_data": init_data})
    assert response.status_code == 200
    return response


def _cookie_morsels(response, name: str):
    morsels = []
    for header in response.headers.get_list("set-cookie"):
        if header.partition("=")[0] == name:
            cookies = SimpleCookie()
            cookies.load(header)
            if name in cookies:
                morsels.append(cookies[name])
    return morsels


def _cookie_has_flag(response, name: str, flag: str, path: str | None = None) -> bool:
    return any(
        bool(cookie[flag]) and (path is None or cookie["path"] == path)
        for cookie in _cookie_morsels(response, name)
    )


def _cookie_attribute_is(
    response,
    name: str,
    attribute: str,
    expected: str,
    path: str | None = None,
) -> bool:
    return any(
        cookie[attribute].lower() == expected.lower()
        and (path is None or cookie["path"] == path)
        for cookie in _cookie_morsels(response, name)
    )


def _response_cookie_matches(response, name: str, token: str) -> bool:
    return any(
        hmac.compare_digest(cookie.value, token)
        for cookie in _cookie_morsels(response, name)
    )


def _cookiejar_entries(client, name: str) -> list[tuple[str, str]]:
    return sorted(
        (cookie.path, cookie.value)
        for cookie in client.cookies.jar
        if cookie.name == name
    )


def _assert_auth_cookiejar(client, tokens: dict) -> None:
    assert _cookiejar_entries(client, "access_token_cookie") == [
        ("/api", tokens["access_token"])
    ]
    assert _cookiejar_entries(client, "refresh_token_cookie") == [
        ("/api/auth/refresh", tokens["refresh_token"])
    ]
    assert not _cookiejar_entries(client, "csrf_access_token")
    assert not _cookiejar_entries(client, "csrf_refresh_token")


def _request_cookie_names(request_cookie_headers, path: str) -> set[str]:
    headers = [
        header
        for request_path, header in request_cookie_headers
        if request_path == path
    ]
    assert headers, f"no request reached {path}"
    cookies = SimpleCookie()
    cookies.load(headers[-1] or "")
    return set(cookies.keys())


def test_login_returns_json_pair_and_sets_scoped_auth_cookies(
    client,
    init_data_factory,
):
    response = _login(client, init_data_factory())
    tokens = response.json()
    access_max_age = str(settings.JWT_ACCESS_TTL_MINUTES * 60)
    refresh_max_age = str(settings.JWT_REFRESH_TTL_DAYS * 24 * 60 * 60)
    same_site = security.config.JWT_COOKIE_SAMESITE

    for cookie_name, token_field, max_age, path in (
        ("access_token_cookie", "access_token", access_max_age, "/api"),
        (
            "refresh_token_cookie",
            "refresh_token",
            refresh_max_age,
            "/api/auth/refresh",
        ),
    ):
        assert _response_cookie_matches(response, cookie_name, tokens[token_field]), (
            "auth cookie must match the JSON token"
        )
        assert _cookie_has_flag(response, cookie_name, "httponly", path), (
            "auth cookie must be HttpOnly"
        )
        assert _cookie_attribute_is(response, cookie_name, "path", path, path), (
            "auth cookie must be scoped to its API route"
        )
        assert _cookie_attribute_is(
            response, cookie_name, "samesite", same_site, path
        ), "auth cookie SameSite must follow configuration"
        assert _cookie_attribute_is(
            response, cookie_name, "max-age", max_age, path
        ), "auth cookie Max-Age must match its token lifetime"

    for cookie_name in ("csrf_access_token", "csrf_refresh_token"):
        assert not any(
            cookie.value for cookie in _cookie_morsels(response, cookie_name)
        )
    _assert_auth_cookiejar(client, tokens)


def test_cookiejar_sends_refresh_only_to_refresh_route(
    client,
    init_data_factory,
    request_cookie_headers,
):
    login = _login(client, init_data_factory())

    me_response = client.get("/api/auth/me")
    products_response = client.get("/api/products")
    refresh_response = client.post("/api/auth/refresh")

    assert me_response.status_code == 200
    assert me_response.json() == login.json()["user"]
    assert products_response.status_code == 501
    assert refresh_response.status_code == 200
    assert "access_token_cookie" in _request_cookie_names(
        request_cookie_headers, "/api/auth/me"
    )
    assert "refresh_token_cookie" not in _request_cookie_names(
        request_cookie_headers, "/api/auth/me"
    )
    assert "access_token_cookie" in _request_cookie_names(
        request_cookie_headers, "/api/products"
    )
    assert "refresh_token_cookie" not in _request_cookie_names(
        request_cookie_headers, "/api/products"
    )
    assert "refresh_token_cookie" in _request_cookie_names(
        request_cookie_headers, "/api/auth/refresh"
    )


def test_refresh_replaces_auth_cookies_without_duplicates(
    client,
    init_data_factory,
):
    login = _login(client, init_data_factory())
    tokens = login.json()

    _assert_auth_cookiejar(client, tokens)

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    rotated = response.json()
    _assert_auth_cookiejar(client, rotated)
    assert _response_cookie_matches(
        response, "access_token_cookie", rotated["access_token"]
    )
    assert _response_cookie_matches(
        response, "refresh_token_cookie", rotated["refresh_token"]
    )


def test_configured_sources_prefer_json_then_cookies_then_headers(
    client,
    init_data_factory,
):
    first_login = _login(client, init_data_factory())
    first_tokens = first_login.json()
    second_login = _login(
        client,
        init_data_factory(telegram_id=987654321),
    )

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {first_tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == second_login.json()["user"]["id"]

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

    client.cookies.clear()
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {first_tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == first_login.json()["user"]["id"]
    for header in ("Bearer invalid", "Bearer"):
        assert client.get(
            "/api/auth/me", headers={"Authorization": header}
        ).status_code == 401


def test_refresh_cookie_works_when_access_is_in_authorization_header(
    client,
    init_data_factory,
):
    tokens = _login(client, init_data_factory()).json()
    response = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    _assert_auth_cookiejar(client, response.json())


def test_invalid_json_refresh_does_not_fall_back_to_valid_cookie(
    client,
    init_data_factory,
):
    tokens = _login(client, init_data_factory()).json()
    response = client.post("/api/auth/refresh", json={"refresh_token": "invalid"})
    assert response.status_code == 401
    _assert_auth_cookiejar(client, tokens)


def test_refresh_without_token_returns_401(client):
    assert client.post("/api/auth/refresh").status_code == 401


@pytest.mark.parametrize(
    ("secure", "same_site"),
    [(False, "lax"), (True, "lax"), (True, "none")],
)
def test_auth_cookie_secure_flag_follows_config(
    client,
    init_data_factory,
    monkeypatch,
    secure,
    same_site,
):
    monkeypatch.setattr(security.config, "JWT_COOKIE_SECURE", secure)
    monkeypatch.setattr(security.config, "JWT_COOKIE_SAMESITE", same_site)

    response = _login(client, init_data_factory())

    for cookie_name, path in (
        ("access_token_cookie", "/api"),
        ("refresh_token_cookie", "/api/auth/refresh"),
    ):
        assert _cookie_has_flag(response, cookie_name, "secure", path) is secure
        assert _cookie_attribute_is(
            response, cookie_name, "samesite", same_site, path
        )
