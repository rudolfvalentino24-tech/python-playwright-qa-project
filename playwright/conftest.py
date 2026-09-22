import json
import os
from pathlib import Path
import random
import uuid
import pytest
from utils.config import storeURL
from utils.storeApi import StoreAPI


CREDENTIALS_FILE = Path(__file__).parent / "data" / "credentials.json"
with open(CREDENTIALS_FILE, encoding="utf-8") as file:
    CREDENTIALS = json.load(file)["user_credentials"]

def pytest_addoption(parser):
    parser.addoption(
        "--browser_name", action="store", default="chrome"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: critical Store UI and API checks")
    config.addinivalue_line("markers", "release: Store release regression")


def pytest_collection_modifyitems(items):
    for item in items:
        if "e2e_bdd" in Path(str(item.path)).parts:
            item.add_marker(pytest.mark.release)


@pytest.fixture(params=CREDENTIALS)
def user_credentials(request):
    """Run a test once for every credential set in credentials.json."""
    return request.param


@pytest.fixture(scope="session")
def admin_credentials():
    """Default admin account from credentials.json for single-user tests."""
    return CREDENTIALS[0]


@pytest.fixture
def browserInstance(playwright, request):
    browser_name = request.config.getoption("browser_name")

    # Jenkins exposes JENKINS_URL automatically.
    # Run headed locally and headless when Jenkins executes the suite.
    headless = os.getenv("JENKINS_URL") is not None or os.getenv("HEADLESS") == "1"

    if browser_name == "chrome":
        browser = playwright.chromium.launch(headless=headless)
    elif browser_name == "firefox":
        browser = playwright.firefox.launch(headless=headless)
    else:
        raise ValueError(f"Unsupported browser_name: {browser_name}")

    context = browser.new_context()
    page = context.new_page()

    yield page

    context.close()
    browser.close()

@pytest.fixture
def e2e_checkout_data():
    unique_id = uuid.uuid4().hex[:8]

    first_names = ["John", "Maria", "Alex", "Anna", "George", "Sofia", "Daniel", "Elena"]
    last_names = ["Tester", "Smith", "Miller", "Brown", "Johnson", "Taylor", "Wilson", "Martin"]

    first_name = random.choice(first_names)
    last_name = random.choice(last_names)

    return {
        "productId": 1,
        "customer": {
            "firstName": first_name,
            "lastName": last_name,
            "email": f"{first_name.lower()}.{last_name.lower()}.{unique_id}@example.com",
            "address": f"Test Street {random.randint(1, 999)}",
            "country": "AT"
        },
        "payment": {
            "cardName": f"{first_name} {last_name}",
            "cardNumber": "4111 1111 1111 1111",
            "expiry": "12/30",
            "cvv": "123"
        }
    }


@pytest.fixture(scope="session")
def viewer_credentials():
    with open(CREDENTIALS_FILE.parent / "viewer_credentials.json", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture(scope="session")
def second_admin_credentials(admin_credentials):
    return next(account for account in CREDENTIALS
                if account["userEmail"] != admin_credentials["userEmail"])


@pytest.fixture(scope="session")
def products():
    with open(CREDENTIALS_FILE.parent / "products.json", encoding="utf-8") as file:
        return json.load(file)


@pytest.fixture
def order_payload(e2e_checkout_data, products):
    return {
        **e2e_checkout_data["customer"],
        "items": [
            {"productId": products[0]["id"], "quantity": 2},
            {"productId": products[1]["id"], "quantity": 1},
        ],
    }


@pytest.fixture
def api_clients(playwright, admin_credentials, viewer_credentials, second_admin_credentials):
    clients = {}
    contexts = []
    accounts = {"admin": admin_credentials, "viewer": viewer_credentials,
                "second admin": second_admin_credentials}

    def get_client(role="admin"):
        if role not in clients:
            context = playwright.request.new_context(base_url=storeURL)
            contexts.append(context)
            clients[role] = StoreAPI(context, accounts[role])
        return clients[role]

    yield get_client
    try:
        order_ids = [order_id for client in clients.values() for order_id in client.order_ids]
        if order_ids:
            admin = get_client("admin")
            for order_id in order_ids:
                response = admin.deleteOrder(order_id)
                assert response.status in (302, 404), f"Cleanup failed for {order_id}"
    finally:
        for context in contexts:
            try:
                context.post("/logout")
            finally:
                context.dispose()


@pytest.fixture
def seeded_order(api_clients, order_payload, products):
    response = api_clients().createOrder(order_payload)
    assert response.status == 201
    items = [
        {**next(product for product in products if product["id"] == item["productId"]),
         "quantity": item["quantity"]}
        for item in order_payload["items"]
    ]
    return {
        "id": response.json()["orderId"],
        "customer": {key: value for key, value in order_payload.items() if key != "items"},
        "items": items,
        "total": round(sum(item["price"] * item["quantity"] for item in items), 2),
    }
