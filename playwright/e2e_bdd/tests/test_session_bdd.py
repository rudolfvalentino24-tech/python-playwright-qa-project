from pytest_bdd import parsers, scenarios, then, when

from pageObjects.cart import CartPage
from pageObjects.login import LoginPage
from pageObjects.ordersHistory import OrdersHistoryPage


scenarios("../features/session.feature")


@when("the admin visits Order History")
def admin_visits_history(browserInstance, shared_data):
    shared_data["orders_page"] = OrdersHistoryPage(browserInstance)
    shared_data["orders_page"].open()


@then("Order History should load successfully")
def history_loads(shared_data):
    shared_data["orders_page"].verifyOrdersLoaded()


@when("the admin returns to the cart")
def admin_returns_to_cart(browserInstance, shared_data):
    LoginPage(browserInstance).openProtectedPage("Cart")
    shared_data["cart_page"] = CartPage(browserInstance)


@then("the cart should retain the selected product")
def cart_retains_product(shared_data):
    shared_data["cart_page"].verifyProduct(shared_data["product"])
    shared_data["cart_page"].verifyTotal([shared_data["product"]])


@when(parsers.parse('the logged-out user opens "{area}"'))
def logged_out_user_opens_page(shared_data, area):
    shared_data["login_page"].openProtectedPage(area, shared_data["order_id"])
