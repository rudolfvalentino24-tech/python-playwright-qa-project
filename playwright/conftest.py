import json
import os
from pathlib import Path
import random
import uuid
import pytest


CREDENTIALS_FILE = Path(__file__).parent / "data" / "credentials.json"
with open(CREDENTIALS_FILE, encoding="utf-8") as file:
    CREDENTIALS = json.load(file)["user_credentials"]

E2E_DATA_FILE = (Path(__file__).parent/"data"/"e2e_checkout.json")

def pytest_addoption(parser):
    parser.addoption(
        "--browser_name", action="store", default="chrome"
    )


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
    headless = os.getenv("JENKINS_URL") is not None

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

    first_names = [
        "John",
        "Maria",
        "Alex",
        "Anna",
        "George",
        "Sofia",
        "Daniel",
        "Elena"
    ]

    last_names = [
        "Tester",
        "Smith",
        "Miller",
        "Brown",
        "Johnson",
        "Taylor",
        "Wilson",
        "Martin"
    ]

    first_name = random.choice(first_names)
    last_name = random.choice(last_names)

    return {
        "productId": 1,

        "customer": {
            "firstName": first_name,
            "lastName": last_name,

            "email": (
                f"{first_name.lower()}."
                f"{last_name.lower()}."
                f"{unique_id}@example.com"
            ),

            "address": (
                f"Test Street "
                f"{random.randint(1, 999)}"
            ),

            "country": "AT"
        },

        "payment": {
            "cardName": (
                f"{first_name} {last_name}"
            ),

            "cardNumber":
                "4111 1111 1111 1111",

            "expiry": "12/30",

            "cvv": "123"
        }
    }

@pytest.fixture(scope="session")
def e2e_checkout_data():
    with open(
        E2E_DATA_FILE,
        encoding="utf-8"
    ) as file:
        return json.load(file)