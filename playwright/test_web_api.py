from playwright.sync_api import Playwright

from pageObjects.login import LoginPage
from utils.apiBaseFramework import APIUtils


def test_E2E_web_api(
    playwright: Playwright,
    browserInstance,
    user_credentials,
):
    username = user_credentials["userEmail"]
    password = user_credentials["userPassword"]

    # Create order through API.
    api_utils = APIUtils()
    order_id = api_utils.createOrder(playwright, user_credentials)

    # Login to Store.
    login_page = LoginPage(browserInstance)
    login_page.navigate()
    dashboard_page = login_page.login(username, password)

    # Open order history.
    order_history_page = dashboard_page.selectOrdersNaviLink()

    # Open the exact order created through the API.
    order_details_page = order_history_page.selectOrder(order_id)

    # Verify the correct order details page is displayed.
    order_details_page.verifyOrderNumber()
