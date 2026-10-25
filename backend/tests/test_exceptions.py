from authx.exceptions import JWTDecodeError, TokenError
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.exceptions import register_exception_handlers


def _exception_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/jwt-error")
    async def jwt_error():
        raise JWTDecodeError("private-jwt-detail")

    @app.get("/token-error")
    async def token_error():
        raise TokenError("private-token-detail")

    @app.get("/http-error")
    async def http_error():
        raise HTTPException(
            status_code=418,
            detail={"message": "teapot"},
            headers={"X-Error-Source": "test"},
        )

    @app.get("/validation")
    async def validation(count: int):
        return {"count": count}

    @app.get("/internal-error")
    async def internal_error():
        raise RuntimeError("private-database-detail")

    return app


def test_authx_jwt_and_token_errors_return_401_with_bearer_challenge():
    with TestClient(_exception_app(), raise_server_exceptions=False) as client:
        for path, private_detail in (
            ("/jwt-error", "private-jwt-detail"),
            ("/token-error", "private-token-detail"),
        ):
            response = client.get(path)

            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer"
            assert isinstance(response.json()["detail"], str)
            assert private_detail not in response.text


def test_http_exception_and_validation_response_keep_fastapi_shape():
    with TestClient(_exception_app(), raise_server_exceptions=False) as client:
        http_response = client.get("/http-error")
        validation_response = client.get("/validation")

    assert http_response.status_code == 418
    assert http_response.json() == {"detail": {"message": "teapot"}}
    assert http_response.headers["x-error-source"] == "test"

    assert validation_response.status_code == 422
    assert validation_response.json()["detail"][0]["loc"] == ["query", "count"]


def test_unexpected_error_hides_response_detail_and_logs_traceback(caplog):
    with TestClient(_exception_app(), raise_server_exceptions=False) as client:
        response = client.get("/internal-error")

    assert response.status_code == 500
    assert response.json() == {"detail": "Внутренняя ошибка сервера"}
    assert "private-database-detail" not in response.text
    assert "private-database-detail" in caplog.text
    assert any(
        record.exc_info and record.exc_info[0] is RuntimeError
        for record in caplog.records
    )
