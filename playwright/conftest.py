import json
import os
from pathlib import Path

import pytest


CREDENTIALS_FILE = Path(__file__).parent / "data" / "credentials.json"
with open(CREDENTIALS_FILE, encoding="utf-8") as file:
    CREDENTIALS = json.load(file)["user_credentials"]


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
