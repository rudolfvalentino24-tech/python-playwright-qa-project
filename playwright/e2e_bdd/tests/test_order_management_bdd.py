from pytest_bdd import scenarios, when


scenarios("../features/order_management.feature")


@when("the admin deletes the created order from Order History and confirms")
def admin_deletes_order_from_history(shared_data):
    shared_data["orders_page"].deleteOrder(shared_data["order_id"])


@when("the admin refreshes Order History")
def admin_refreshes_order_history(shared_data):
    shared_data["orders_page"].refresh()
