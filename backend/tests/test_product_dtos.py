import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.catalog.adapters.magnit import parse_product, request
from app.catalog.adapters.schemas import ProductData
from app.catalog.schemas import CategoryFilters, ProductFilters
from app.notifications.schemas import NotificationCreate
from app.tracking.schemas import TrackingCreate, TrackingFilters


@pytest.mark.parametrize(
    "invalid_field",
    [
        {"price_kopecks": -1},
        {"discount_percent": -1},
        {"discount_percent": 101},
        {"status": "unknown"},
        {"product_name": ""},
    ],
)
def test_notification_dto_validates_values_before_saving(invalid_field):
    values = {
        "user_id": 1,
        "product_name": "Товар",
        "store_name": "Магнит",
        "discount_percent": 30,
    }
    assert NotificationCreate(**values).status == "pending"
    with pytest.raises(ValidationError):
        NotificationCreate(**(values | invalid_field))


def test_catalog_and_tracking_query_dtos_validate_filter_bounds():
    assert CategoryFilters(store_id=1).store_id == 1
    assert TrackingFilters(page=2, page_size=50).page_size == 50
    assert ProductFilters(min_price=Decimal("1"), max_price=Decimal("2")).max_price == 2

    with pytest.raises(ValidationError):
        CategoryFilters(store_id=0)
    with pytest.raises(ValidationError):
        TrackingFilters(page=0)
    with pytest.raises(ValidationError):
        ProductFilters(page_size=101)
    with pytest.raises(
        ValidationError, match="min_price не может быть больше max_price"
    ):
        ProductFilters(min_price=Decimal("10"), max_price=Decimal("9"))


def test_tracking_and_adapter_dtos_reject_invalid_targets_and_money():
    with pytest.raises(ValidationError, match="ровно одно поле"):
        TrackingCreate(min_discount_percent=20)
    with pytest.raises(ValidationError, match="ровно одно поле"):
        TrackingCreate(product_id=1, category_id=2, min_discount_percent=20)

    product = ProductData(
        external_id="product-1",
        name="Товар",
        current_price_kopecks=1999,
        discount_percent=Decimal("20.00"),
    )
    assert product.current_price_kopecks == 1999

    with pytest.raises(ValidationError):
        ProductData(external_id="product-2", name="Товар", current_price_kopecks=-1)
    with pytest.raises(ValidationError):
        ProductData(external_id="product-3", name="Товар", discount_percent=101)


def test_magnit_adapter_stubs_raise_not_implemented():
    with pytest.raises(NotImplementedError):
        parse_product({})

    with pytest.raises(NotImplementedError):
        asyncio.run(request())


def test_get_contracts_use_query_parameters_and_reject_invalid_ranges(client):
    openapi = client.get("/openapi.json").json()
    for path in ("/api/stores", "/api/categories", "/api/products", "/api/tracking"):
        assert "requestBody" not in openapi["paths"][path]["get"]

    category_parameters = {
        parameter["name"]: parameter["in"]
        for parameter in openapi["paths"]["/api/categories"]["get"]["parameters"]
    }
    product_parameters = {
        parameter["name"]: parameter["in"]
        for parameter in openapi["paths"]["/api/products"]["get"]["parameters"]
    }
    assert category_parameters["store_id"] == "query"
    assert product_parameters["min_price"] == "query"
    assert product_parameters["max_price"] == "query"

    invalid_category = client.get("/api/categories", params={"store_id": 0})
    invalid_range = client.get(
        "/api/products", params={"min_price": "10", "max_price": "9"}
    )
    valid_query = client.get(
        "/api/products", params={"store_id": 1, "min_price": "1", "max_price": "10"}
    )

    assert invalid_category.status_code == 422
    assert invalid_range.status_code == 422
    assert valid_query.status_code == 501
