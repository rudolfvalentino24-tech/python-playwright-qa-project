import json
import pytest
from pathlib import Path
from playwright.sync_api import Playwright
from utils.apiBase import APIUtils
from pageObjects.login import LoginPage

credentials_file = Path(__file__).parent / "data" / "credentials.json"
with open(credentials_file) as f:
    test_data = json.load(f)
    user_credentials_list = test_data["user_credentials"]

@pytest.mark.parametrize('user_credentials', user_credentials_list)
def test_E2E_web_api(playwright: Playwright, browserInstance,user_credentials):

    # Store credentials in variables
    username = user_credentials["userEmail"]
    password = user_credentials["userPassword"]

    # Create order through API
    api_utils = APIUtils()
    order_id = api_utils.createOrder(playwright, user_credentials)

    # Login to STORE and save the returned dashboard in a variable
    loginPage = LoginPage(browserInstance)
    loginPage.navigate()
    dashboardPage = loginPage.login(username, password)

    # Open order history
    orderHistoryPage = dashboardPage.selectOerdersNaviLink()

    # Open the exact order created through API
    oderDetailsPage = orderHistoryPage.selectOrder(order_id)

    # Verify API-created order exists in UI
    oderDetailsPage.verifyOrderMessage()