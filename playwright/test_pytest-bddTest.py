import pytest
from pytest_bdd import given, when, then, parsers, scenarios
from conftest import browserInstance
from pageObjects.login import LoginPage
from utils.apiBaseFramework import APIUtils

scenarios('features/orderTransaction.feature')

@pytest.fixture
def shared_data():
    return {}

@given(parsers.parse('place the item order with {username} and {password}'))
def place_item_order(playwright, username, password, shared_data):
    user_credentials = {
        "userEmail": username,
        "userPassword": password
    }
    api_utils = APIUtils()
    order_id = api_utils.createOrder(playwright, user_credentials)
    shared_data["order_id"] = order_id

@given('the user is on the landing page')
def user_on_landing_page(browserInstance, shared_data):
    loginPage = LoginPage(browserInstance)
    loginPage.navigate()
    shared_data['login_page'] = loginPage

@when(parsers.parse('I login to portal with {username} and {password}'))
def login_to_portal(username, password, shared_data):
    loginPage = shared_data['login_page']
    dashboardPage = loginPage.login(username, password)
    shared_data['dashboard_page'] = dashboardPage

@when('navigate to orders page')
def navigate_to_orders_page(shared_data):
    dashboardPage = shared_data['dashboard_page']
    orderHistoryPage = dashboardPage.selectOerdersNaviLink()
    shared_data['orderHistory_page'] = orderHistoryPage

@when('select the orderID')
def select_order_id(shared_data):
    orderHistoryPage = shared_data['orderHistory_page']
    orderId = shared_data['order_id']
    oderDetailsPage = orderHistoryPage.selectOrder(orderId)
    shared_data['orderDetails_page'] = oderDetailsPage

@then('order message is successfully displayed')
def order_message_successfully_displayed(shared_data):
    oderDetailsPage = shared_data['orderDetails_page']
    oderDetailsPage.verifyOrderMessage()