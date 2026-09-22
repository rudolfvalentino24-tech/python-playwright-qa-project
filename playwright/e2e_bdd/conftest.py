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

@then("the Store page should be displayed")
def store_page_is_displayed(shared_data):
    shared_data["dashboard_page"].verifyStorePage()

@given("the admin is logged in")
def admin_is_logged_in(browserInstance, admin_credentials, shared_data):
    login_page = LoginPage(browserInstance)
    login_page.navigate()
    shared_data["dashboard_page"] = login_page.login(
        admin_credentials["userEmail"], admin_credentials["userPassword"]
    )

@given("the admin has added a product to the cart")
def admin_has_added_product(admin_credentials, browserInstance, e2e_checkout_data, shared_data):
    login_page = LoginPage(browserInstance)
    login_page.navigate()

    dashboard_page = login_page.login(
        admin_credentials["userEmail"], admin_credentials["userPassword"]
    )

    product = dashboard_page.addProductToCart(e2e_checkout_data["productId"])

    shared_data["dashboard_page"] = dashboard_page
    shared_data["product"] = product


@given("the admin has added multiple products to the cart")
def admin_has_added_multiple_products(admin_credentials, browserInstance, shared_data):
    login_page = LoginPage(browserInstance)
    login_page.navigate()

    dashboard_page = login_page.login(
        admin_credentials["userEmail"], admin_credentials["userPassword"]
    )

    first_product = dashboard_page.addProductToCart(1)
    second_product = dashboard_page.addProductToCart(2)

    shared_data["dashboard_page"] = dashboard_page
    shared_data["products"] = [first_product, second_product]

@when("the admin adds a product to the cart")
def admin_adds_product(e2e_checkout_data, shared_data):

    shared_data["product"] = shared_data["dashboard_page"].addProductToCart(e2e_checkout_data["productId"])

@when("the admin opens the cart")
def admin_opens_cart(shared_data):
    shared_data["cart_page"] = shared_data["dashboard_page"].openCart()