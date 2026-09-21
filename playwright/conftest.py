import os
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--browser_name", action="store", default="chrome"
    )


@pytest.fixture(scope='session')
def user_credentials(request):
    return request.param


@pytest.fixture
def browserInstance(playwright, request):

    browser_name = request.config.getoption("browser_name")

    # Jenkins sets CI=true in the build environment
    headless = os.getenv("CI", "false").lower() == "true"

    if browser_name == "chrome":
        browser = playwright.chromium.launch(
            headless=headless
        )

    elif browser_name == "firefox":
        browser = playwright.firefox.launch(
            headless=headless
        )

    context = browser.new_context()
    page = context.new_page()

    yield page

    context.close()
    browser.close()
