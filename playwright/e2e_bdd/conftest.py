import pytest
from pytest_bdd import given, when, then
from pageObjects.login import LoginPage
from pageObjects.ordersHistory import OrdersHistoryPage

@pytest.fixture
def shared_data(browserInstance, api_clients):
    data = {}
    yield data
    if data.get("order_id"):
        response = api_clients().deleteOrder(data["order_id"])
        assert response.status in (302, 404), "Failed to clean up the scenario's order"

@given("the user is on the login page")
def user_on_login_page(browserInstance, shared_data):
    login_page = LoginPage(browserInstance)
    login_page.navigate()
    login_page.verifyLoginPage()
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


@when("the admin proceeds to checkout")
def admin_proceeds_to_checkout(shared_data):
    shared_data["total"] = shared_data["cart_page"].getTotal()
    shared_data["checkout_page"] = shared_data["cart_page"].proceedToCheckout()


@then("the checkout page should be displayed")
def checkout_page_is_displayed(shared_data):
    shared_data["checkout_page"].verifyCheckoutPage()


@when("the admin enters valid checkout information")
def admin_enters_checkout_information(e2e_checkout_data, shared_data):
    shared_data["checkout_page"].enterCheckoutInformation(
        e2e_checkout_data["customer"], e2e_checkout_data["payment"]
    )


@when("the admin places the order")
def admin_places_order(shared_data):
    shared_data["confirmation_page"] = shared_data["checkout_page"].placeOrder()


@then("the order should be created successfully")
def order_created_successfully(shared_data):
    shared_data["confirmation_page"].verifyOrderSuccess()


@then("an order number should be displayed")
def order_number_displayed(shared_data):
    shared_data["order_id"] = shared_data["confirmation_page"].getOrderNumber()


@when("the admin navigates to order history")
def navigate_to_order_history(shared_data):
    shared_data["orders_page"] = shared_data["confirmation_page"].openOrderHistory()


@then("the created order should appear in the order history")
def created_order_appears(shared_data):
    shared_data["orders_page"].verifyOrderExists(shared_data["order_id"])


@when("the admin opens the created order")
@when("the viewer opens the created order")
def open_created_order(shared_data):
    shared_data["details_page"] = shared_data["orders_page"].selectOrder(
        shared_data["order_id"]
    )


@then("the correct order number should be displayed")
def verify_order_number(shared_data):
    shared_data["details_page"].verifyOrderNumber()


@given("an order exists for permission checks")
def order_exists_for_permissions(seeded_order, shared_data):
    shared_data["order_id"] = seeded_order["id"]
    shared_data["seeded_order"] = seeded_order


@given("the orders viewer is logged in")
def viewer_is_logged_in(browserInstance, viewer_credentials, shared_data):
    login = LoginPage(browserInstance)
    login.navigate()
    shared_data["login_page"] = login
    shared_data["orders_page"] = login.loginAsViewer(viewer_credentials)


@when("the admin deletes the order from Order Details and confirms")
def admin_deletes_order_from_details(shared_data):
    shared_data["details_page"].deleteOrder()


@then("the deleted order should not appear in Order History")
def deleted_order_is_absent(shared_data):
    shared_data["orders_page"].verifyOrderRemoved(shared_data["order_id"])


@when("the user logs out from Order History")
def user_logs_out_from_order_history(browserInstance, shared_data):
    OrdersHistoryPage(browserInstance).logout()
    shared_data["login_page"] = LoginPage(browserInstance)


@when("the second admin logs in")
def second_admin_logs_in(second_admin_credentials, shared_data):
    shared_data["dashboard_page"] = shared_data["login_page"].login(
        second_admin_credentials["userEmail"], second_admin_credentials["userPassword"]
    )


@when("the admin opens Order History from the Store")
def admin_opens_history_from_store(shared_data):
    shared_data["orders_page"] = shared_data["dashboard_page"].selectOrdersNaviLink()
