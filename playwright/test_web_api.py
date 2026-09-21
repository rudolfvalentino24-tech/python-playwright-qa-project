import json
import pytest
from pathlib import Path
from playwright.sync_api import Playwright, expect

from pageObjects.dashboard import DashboardPage
from utils.apiBase import APIUtils
from utils.config import storeURL
from pageObjects.login import LoginPage

credentials_file = Path(__file__).parent / "data" / "credentials.json"
with open(credentials_file) as f:
    test_data = json.load(f)
    user_credentials_list = test_data["user_credentials"]

@pytest.mark.parametrize('user_credentials', user_credentials_list)
def test_E2E_web_api(playwright: Playwright, user_credentials):
    # Store credentials in variables
    username = user_credentials["userEmail"]
    password = user_credentials["userPassword"]

    # Create order through API
    api_utils = APIUtils()
    order_id = api_utils.createOrder(playwright, user_credentials)

    # Open browser
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # Login to STORE and save the returned dashboard in a variable
    loginPage = LoginPage(page)
    loginPage.navigate()
    dashboardPage = loginPage.login(username, password)

    expect(page).to_have_url(
        f"{storeURL}/store"
    )

    # Open order history
    dashboardPage.selectOerdersNaviLink()


    # Verify API-created order exists in UI
    expect(
        page.get_by_text(order_id, exact=True)
    ).to_be_visible()

    browser.close()