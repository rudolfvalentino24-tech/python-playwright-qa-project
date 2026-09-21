from playwright.sync_api import Page, Playwright
from utils.apiBaseFramework import APIUtils
from utils.config import storeURL

fakePayloadOrderResponse = {
    "data": [], "message": "No orders yet"
}

def intercept_response(route):
    route.fulfill(
        json = fakePayloadOrderResponse
    )

def test_Network(page: Page):
    page.goto(storeURL)
    page.route("**/api/orders",intercept_response)

    page.get_by_label("Username").fill("tester")
    page.get_by_label("Password").fill("password123")
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()
    page.get_by_test_id("orders-link").click()
    order_text = page.get_by_test_id("no-orders-heading").text_content().strip()
    assert order_text == "No orders yet"
    print(order_text)

def test_sessionStorage(playwright: Playwright):
    api_utils = APIUtils()
    getToken = api_utils.getToken(playwright)
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    #script to inject token in session local storage
    page.add_init_script(f"""localStorage.setItem('authToken', '{getToken}');""")
    page.goto(f"{storeURL}/orders")

