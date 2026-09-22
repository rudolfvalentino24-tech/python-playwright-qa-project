import pytest
from pytest_bdd import given, when, then, scenarios
from pageObjects.login import LoginPage

scenarios("../features/storePurchase.feature")

@pytest.fixture
def shared_data():
    return {}

@given("the admin is on the login page")
def admin_on_login_page(browserInstance, shared_data):

    login_page = LoginPage(browserInstance)
    login_page.navigate()
    shared_data["login_page"] = login_page

@when("the admin logs in")
def admin_logs_in(admin_credentials, shared_data):

    shared_data["dashboard_page"] = shared_data["login_page"].login(
        admin_credentials["userEmail"],
        admin_credentials["userPassword"]
    )

@when("the admin adds a product to the cart")
def admin_adds_product(e2e_checkout_data, shared_data):

    shared_data["product"] = shared_data["dashboard_page"].addProductToCart(e2e_checkout_data["productId"])

@when("the admin opens the cart")
def admin_opens_cart(shared_data):

    cart_page = shared_data["dashboard_page"].openCart()
    cart_page.verifyProduct(shared_data["product"])
    shared_data["total"] = cart_page.getTotal()
    shared_data["cart_page"] = cart_page

@when("the admin proceeds to checkout")
def admin_proceeds_to_checkout(shared_data):

    shared_data["checkout_page"] = (shared_data["cart_page"].proceedToCheckout())

@when("the admin enters valid checkout information")
def admin_enters_checkout_information(e2e_checkout_data, shared_data):

    shared_data["checkout_page"].enterCheckoutInformation(e2e_checkout_data["customer"],e2e_checkout_data["payment"])

@when("the admin places the order")
def admin_places_order(shared_data):

    shared_data["confirmation_page"] = (shared_data["checkout_page"].placeOrder())

@then("the order should be created successfully")
def order_created_successfully(shared_data):

    shared_data["confirmation_page"].verifyOrderSuccess()

@then("an order number should be displayed")
def order_number_displayed(shared_data):

    shared_data["order_id"] = (shared_data["confirmation_page"].getOrderNumber())

@when("the admin navigates to order history")
def navigate_to_order_history(shared_data):

    shared_data["orders_page"] = (shared_data["confirmation_page"].openOrderHistory())

@then("the created order should appear in the order history")
def created_order_appears(shared_data):

    shared_data["orders_page"].verifyOrderExists(shared_data["order_id"])

@when("the admin opens the created order")
def open_created_order(shared_data):

    shared_data["details_page"] = (shared_data["orders_page"].selectOrder(shared_data["order_id"]))

@then("the correct order number should be displayed")
def verify_order_number(shared_data):

    shared_data["details_page"].verifyOrderNumber(shared_data["order_id"])

@then("the correct product should be displayed")
def verify_product(shared_data):

    shared_data["details_page"].verifyProduct(shared_data["product"])

@then("the correct customer information should be displayed")
def verify_customer(e2e_checkout_data, shared_data):

    shared_data["details_page"].verifyCustomer(e2e_checkout_data["customer"])

@then("the correct total should be displayed")
def verify_total(shared_data):

    shared_data["details_page"].verifyTotal(shared_data["total"])