from pytest_bdd import parsers, scenarios, then, when

scenarios("../features/authorization.feature")

@when("the user tries to access the Store page without authentication")
def user_accesses_store_without_authentication(shared_data):
    shared_data["login_page"].openProtectedStorePage()


@when("the orders viewer logs in")
def viewer_logs_in(viewer_credentials, shared_data):
    shared_data["orders_page"] = shared_data["login_page"].loginAsViewer(viewer_credentials)


@then("Order History should be displayed for the viewer")
def viewer_sees_history(shared_data):
    shared_data["orders_page"].verifyOrdersLoaded()


@when(parsers.parse('the viewer opens the protected "{area}" page'))
def viewer_opens_protected_page(shared_data, area):
    shared_data["login_page"].openProtectedPage(area)


@then("Order History should offer no admin controls")
def history_is_read_only(shared_data):
    shared_data["orders_page"].verifyReadOnly()


@then("Order Details should offer no deletion control")
def details_are_read_only(shared_data):
    shared_data["details_page"].verifyReadOnly()


@then("the viewer should see the purchased items and total")
def viewer_sees_order_details(shared_data):
    order = shared_data["seeded_order"]
    shared_data["details_page"].verifyProducts(order["items"])
    shared_data["details_page"].verifyTotal(order["total"])
