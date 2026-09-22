from pytest_bdd import parsers, scenarios, then, when


scenarios("../features/checkout.feature")


@when(parsers.parse('the admin leaves the "{field}" checkout field empty'))
def admin_leaves_checkout_field_empty(shared_data, field):
    shared_data["checkout_page"].clearField(field)


@when("the admin unchecks the order confirmation")
def admin_unchecks_order_confirmation(shared_data):
    shared_data["checkout_page"].uncheckOrderConfirmation()


@when(parsers.parse('the admin enters "{email}" as the checkout email'))
def admin_enters_checkout_email(shared_data, email):
    shared_data["checkout_page"].setEmail(email)


@when("the admin attempts to place the order")
def admin_attempts_to_place_order(shared_data):
    shared_data["checkout_page"].submitOrder()


@then("the checkout submission should be blocked")
def checkout_submission_is_blocked(shared_data):
    shared_data["checkout_page"].verifySubmissionBlocked()


@then(parsers.parse('the "{field}" checkout field should be required'))
def checkout_field_is_required(shared_data, field):
    shared_data["checkout_page"].verifyFieldValidation(field, "valueMissing")


@then("the checkout email should be invalid")
def checkout_email_is_invalid(shared_data):
    shared_data["checkout_page"].verifyFieldValidation("email", "typeMismatch")


@then("the cart total should match the selected product prices")
def cart_total_matches_selected_product_prices(shared_data):
    shared_data["cart_page"].verifyTotal(shared_data["products"])


@then("the checkout total should match the cart total")
def checkout_total_matches_cart(shared_data):
    shared_data["checkout_page"].verifyTotal(shared_data["total"])


@then("the checkout total should equal the sum of the selected product prices")
def checkout_total_matches_selected_product_prices(shared_data):
    expected_total = sum(product["price"] for product in shared_data["products"])
    shared_data["checkout_page"].verifyTotal(expected_total)
