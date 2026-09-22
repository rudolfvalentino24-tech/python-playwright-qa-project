import json
import re
import uuid

import pytest

from utils.config import storeURL


pytestmark = pytest.mark.release

CUSTOMER_FIELDS = ("firstName", "lastName", "email", "address", "country")


@pytest.fixture
def customer_validation_payload(order_payload):
    # A second unique marker lets us find accidental orders even when email is invalid.
    return {**order_payload, "address": f"Validation Street {uuid.uuid4().hex}"}


def assert_order_rejected_without_creation(client, payload, expected_fields):
    response = client.createOrder(payload)
    assert response.status == 400, f"Invalid order was accepted (HTTP {response.status})"
    body = response.json()
    assert body["error"]
    assert "orderId" not in body
    if expected_fields:
        assert set(body["fields"]) == set(expected_fields)

    # Check this request's unique marker, so unrelated orders do not affect the test.
    marker_field = "email" if isinstance(payload.get("email"), str) and payload["email"].strip() else "address"
    orders = client.getOrders()
    assert orders.status == 200
    assert all(order[marker_field] != payload[marker_field] for order in orders.json()["orders"])


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


@pytest.mark.parametrize("field", [*CUSTOMER_FIELDS, "items"])
def test_required_order_data_is_rejected_when_missing(api_clients, customer_validation_payload, field):
    """REL-API-ORD-09: required customer/order data must also be validated server-side."""
    customer_validation_payload.pop(field)
    assert_order_rejected_without_creation(
        api_clients(), customer_validation_payload, [field] if field in CUSTOMER_FIELDS else []
    )


@pytest.mark.parametrize("field", CUSTOMER_FIELDS)
@pytest.mark.parametrize("value", [
    pytest.param(None, id="null"),
    pytest.param("", id="empty"),
    pytest.param(" \t\n ", id="whitespace"),
    pytest.param(123, id="number"),
    pytest.param(True, id="boolean"),
    pytest.param([], id="array"),
    pytest.param({}, id="object"),
])
def test_required_customer_fields_reject_invalid_values(api_clients, customer_validation_payload, field, value):
    customer_validation_payload[field] = value
    assert_order_rejected_without_creation(api_clients(), customer_validation_payload, [field])


def test_all_invalid_customer_fields_are_reported(api_clients, customer_validation_payload):
    # Keep email/address markers intact while invalidating multiple other fields.
    for field in ("firstName", "lastName", "country"):
        customer_validation_payload.pop(field)
    assert_order_rejected_without_creation(
        api_clients(), customer_validation_payload, ["firstName", "lastName", "country"]
    )


def test_valid_customer_fields_are_trimmed(api_clients, order_payload):
    expected = {field: order_payload[field] for field in CUSTOMER_FIELDS}
    for field in CUSTOMER_FIELDS:
        order_payload[field] = f"  {expected[field]}  "
    client = api_clients()
    response = client.createOrder(order_payload)
    assert response.status == 201
    orders = client.getOrders()
    assert orders.status == 200
    matches = [order for order in orders.json()["orders"]
               if order["order_number"] == response.json()["orderId"]]
    assert len(matches) == 1
    order = matches[0]
    assert order["customer_name"] == f"{expected['firstName']} {expected['lastName']}"
    for field in ("email", "address", "country"):
        assert order[field] == expected[field]


@pytest.mark.parametrize("payload", [None, ["not", "an", "object"], "not an object"])
def test_order_body_must_be_a_json_object(api_clients, payload):
    client = api_clients()
    response = client.request.post("/api/orders", data=json.dumps(payload), headers={
        **client.headers, "Content-Type": "application/json",
    })
    assert response.status == 400
    assert response.json()["error"] == "Request body must be a JSON object"


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
