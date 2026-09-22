import re

import pytest

from utils.config import storeURL


pytestmark = pytest.mark.release


@pytest.fixture
def anonymous_request(playwright):
    request = playwright.request.new_context(base_url=storeURL)
    yield request
    request.dispose()


@pytest.mark.smoke
@pytest.mark.parametrize("role, expected_role", [
    pytest.param("admin", "admin", id="REL-API-AUTH-01-admin"),
    pytest.param("viewer", "orders_viewer", id="REL-API-AUTH-02-viewer"),
])
def test_login_token_and_identity(api_clients, role, expected_role):
    client = api_clients(role)
    assert client.identity["token_type"] == "Bearer"
    response = client.getUser()
    assert response.status == 200
    assert response.json() == {
        "username": client.identity["username"],
        "role": expected_role,
        "authenticated": True,
    }
    assert client.identity["role"] == expected_role


@pytest.mark.parametrize("field, value", [
    pytest.param("username", "nonexistent-qa-user", id="REL-API-AUTH-03", marks=pytest.mark.smoke),
    pytest.param("password", "incorrect-password", id="REL-API-AUTH-04", marks=pytest.mark.smoke),
    pytest.param("username", None, id="REL-API-AUTH-05"),
    pytest.param("password", None, id="REL-API-AUTH-06"),
])
def test_login_rejects_invalid_or_missing_credentials(anonymous_request, admin_credentials, field, value):
    form = {"username": admin_credentials["userEmail"], "password": admin_credentials["userPassword"]}
    if value is None:
        form.pop(field)
    else:
        form[field] = value
    response = anonymous_request.post("/login", form=form)
    assert response.status == 401
    assert "token" not in response.json()
    assert response.json()["error"]


@pytest.mark.smoke
@pytest.mark.parametrize("reader_role", ["admin", "viewer"])
def test_created_order_is_listed_with_correct_details(api_clients, seeded_order, reader_role):
    """REL-API-ORD-01..07: create, identify, retrieve, and verify order integrity."""
    order_id = seeded_order["id"]
    assert re.fullmatch(r"TEST-\d+", order_id)
    response = api_clients(reader_role).getOrders()
    assert response.status == 200
    matches = [order for order in response.json()["orders"] if order["order_number"] == order_id]
    assert len(matches) == 1
    order = matches[0]
    assert order["items"] == seeded_order["items"]
    assert order["total"] == seeded_order["total"]
    customer = seeded_order["customer"]
    assert order["customer_name"] == f"{customer['firstName']} {customer['lastName']}"
    for field in ("email", "address", "country"):
        assert order[field] == customer[field]


@pytest.mark.parametrize("items, expected_status", [
    pytest.param([], 400, id="REL-API-ORD-09-no-items"),
    pytest.param([{"productId": "invalid", "quantity": 1}], 400, id="REL-API-ORD-08-invalid-product-id"),
    pytest.param([{"productId": 1, "quantity": "invalid"}], 400, id="REL-API-ORD-08-invalid-quantity"),
    pytest.param([{"productId": 999999, "quantity": 1}], 404, id="REL-API-ORD-08-unknown-product"),
])
def test_invalid_order_items_are_rejected(api_clients, order_payload, items, expected_status):
    order_payload["items"] = items
    response = api_clients().createOrder(order_payload)
    assert response.status == expected_status
    assert response.json()["error"]


@pytest.mark.parametrize("field", ["firstName", "lastName", "email", "address", "country", "items"])
def test_required_order_data_is_rejected_when_missing(api_clients, order_payload, field):
    """REL-API-ORD-09: required customer/order data must also be validated server-side."""
    order_payload.pop(field)
    response = api_clients().createOrder(order_payload)
    assert response.status == 400, f"Missing {field} was accepted (HTTP {response.status})"
    assert response.json()["error"]


@pytest.mark.smoke
def test_viewer_cannot_create_order(api_clients, order_payload):
    """ROLE-06 / REL-API-ORD-10 / SMK-API-08."""
    response = api_clients("viewer").createOrder(order_payload)
    assert response.status == 403
    assert response.json()["error"] == "Admin access required"


def test_viewer_cannot_delete_order_by_direct_request(api_clients, seeded_order):
    """ROLE-07: hiding Delete is insufficient; the server must protect the route."""
    response = api_clients("viewer").deleteOrder(seeded_order["id"])
    assert response.status == 302
    assert response.headers["location"] == "/orders"
    orders = api_clients().getOrders()
    assert orders.status == 200
    assert any(order["order_number"] == seeded_order["id"] for order in orders.json()["orders"])


def test_viewer_cannot_submit_checkout_directly(api_clients, order_payload):
    """ROLE-06: protect cookie-authenticated checkout as well as the bearer API."""
    viewer = api_clients("viewer")
    add_response = viewer.request.post("/add-to-cart/1", max_redirects=0)
    assert add_response.status == 302
    assert add_response.headers["location"] == "/orders"
    response = viewer.request.post("/checkout", form={
        "first_name": order_payload["firstName"], "last_name": order_payload["lastName"],
        "email": order_payload["email"], "address": order_payload["address"],
        "country": order_payload["country"],
    }, max_redirects=0)
    assert response.status == 302
    assert response.headers["location"] == "/orders"
    orders = api_clients().getOrders()
    assert orders.status == 200
    assert all(order["email"] != order_payload["email"] for order in orders.json()["orders"])


@pytest.mark.smoke
@pytest.mark.parametrize("endpoint", ["/api/user", "/api/orders"])
@pytest.mark.parametrize("token", [None, "invalid-token"], ids=["missing-token", "SESSION-04-invalid-token"])
def test_api_rejects_missing_or_invalid_token(anonymous_request, endpoint, token):
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    response = anonymous_request.get(endpoint, headers=headers)
    assert response.status == 401
    assert response.json()["error"]


@pytest.mark.parametrize("token", [None, "invalid-token"], ids=["missing-token", "invalid-token"])
def test_order_creation_requires_valid_token(anonymous_request, order_payload, token):
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    response = anonymous_request.post("/api/orders", data=order_payload, headers=headers)
    assert response.status == 401


@pytest.mark.parametrize("endpoint", ["/api/user", "/api/orders"])
def test_expired_token_is_rejected(api_clients, endpoint):
    """SESSION-03 / REL-API-SEC-03: prove the same token works before expiration."""
    admin = api_clients()
    assert admin.request.get(endpoint, headers=admin.headers).status == 200
    admin.expireToken()
    response = admin.request.get(endpoint, headers=admin.headers)
    assert response.status == 401


def test_logout_revokes_bearer_token(api_clients):
    admin = api_clients()
    assert admin.getUser().status == 200
    assert admin.request.post("/logout", max_redirects=0).status == 302
    assert admin.getUser().status == 401
