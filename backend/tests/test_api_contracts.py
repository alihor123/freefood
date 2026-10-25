def test_openapi_documents_bearer_auth_and_has_no_logout(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    paths = schema["paths"]
    assert "/api/auth/logout" not in paths

    schemes = schema.get("components", {}).get("securitySchemes", {})
    bearer_name = next(
        (
            name
            for name, scheme in schemes.items()
            if scheme.get("type") == "http" and scheme.get("scheme") == "bearer"
        ),
        None,
    )
    assert bearer_name is not None

    for path, method in (("/api/auth/me", "get"), ("/api/tracking", "get")):
        operation = paths[path][method]
        assert any(bearer_name in requirement for requirement in operation["security"])


def test_tracking_requires_authentication_before_not_implemented_response(
    client,
    init_data_factory,
):
    client.cookies.clear()
    unauthenticated = client.get("/api/tracking")
    assert unauthenticated.status_code == 401

    login = client.post(
        "/api/auth/telegram",
        json={"init_data": init_data_factory()},
    )
    assert login.status_code == 200
    authorized = client.get(
        "/api/tracking",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert authorized.status_code == 501
