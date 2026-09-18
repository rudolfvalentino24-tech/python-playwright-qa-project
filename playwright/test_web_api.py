from playwright.sync_api import Playwright, expect
from utils.apiBase import APIUtils
from utils.config import storeURL


def test_E2E_web_api(playwright: Playwright):

    # Create order through API
    api_utils = APIUtils()
    order_id = api_utils.createOrder(playwright)

    # Open browser
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # Login to STORE
    page.goto(storeURL)

    page.get_by_label("Username").fill("tester")
    page.get_by_label("Password").fill("password123")
    page.locator("#termsCheckbox").check()
    page.get_by_role("button",name="Login").click()

    expect(page).to_have_url(
        f"{storeURL}/store"
    )

    # Open order history
    page.get_by_test_id("orders-link").click()

    # Verify API-created order exists in UI
    expect(
        page.get_by_text(order_id, exact=True)
    ).to_be_visible()

    browser.close()