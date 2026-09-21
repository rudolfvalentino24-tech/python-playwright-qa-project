from playwright.sync_api import Page, expect

from utils.apiBaseFramework import APIUtils
from utils.config import storeURL


fakePayloadOrderResponse = {
    "data": [],
    "message": "No orders yet",
}


def intercept_response(route):
    route.fulfill(json=fakePayloadOrderResponse)


def test_Network(page: Page, admin_credentials):
    page.goto(storeURL)
    page.route("**/api/orders", intercept_response)

    page.get_by_label("Username").fill(admin_credentials["userEmail"])
    page.get_by_label("Password").fill(admin_credentials["userPassword"])
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()
    page.get_by_test_id("orders-link").click()

    expect(page.get_by_test_id("no-orders-heading")).to_have_text("No orders yet")


def test_sessionStorage(browserInstance, admin_credentials):
    page = browserInstance
    api_utils = APIUtils()

    # Authenticate through the BrowserContext so the Flask session cookie and
    # bearer token belong to the same browser session.
    token = api_utils.getTokenForBrowserContext(
        page.context,
        admin_credentials,
    )

    # Inject the bearer token before the page's JavaScript executes.
    page.add_init_script(
        f"""localStorage.setItem('authToken', '{token}');"""
    )

    page.goto(f"{storeURL}/orders")

    expect(page).to_have_url(f"{storeURL}/orders")
    expect(page.get_by_test_id("orders-container")).to_be_visible()
