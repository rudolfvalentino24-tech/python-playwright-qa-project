import pytest
from pytest_bdd import given, when, then
from pageObjects.login import LoginPage

@pytest.fixture
def shared_data():
    return {}

@given("the user is on the login page")
def user_on_login_page(browserInstance, shared_data):
    login_page = LoginPage(browserInstance)
    login_page.navigate()
    shared_data["login_page"] = login_page

@when("the admin logs in with valid credentials")
def admin_logs_in_with_credentials(admin_credentials, shared_data):
    shared_data["dashboard_page"] = shared_data["login_page"].login(
        admin_credentials["userEmail"], admin_credentials["userPassword"])

@then("the login page should be displayed")
def login_page_is_displayed(shared_data):
    shared_data["login_page"].verifyLoginPage()