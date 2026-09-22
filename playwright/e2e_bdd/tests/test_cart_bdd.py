from pytest_bdd import scenario, when, then


@scenario("../features/cart.feature", "CART-01 Add one product to cart")
def test_CART_01():
    pass


@scenario("../features/cart.feature", "CART-02 Add multiple products to cart")
def test_CART_02():
    pass


@scenario("../features/cart.feature", "CART-03 Cart displays correct product information")
def test_CART_03():
    pass


@scenario("../features/cart.feature", "CART-04 Cart total is calculated correctly")
def test_CART_04():
    pass


@scenario("../features/cart.feature", "CART-05 Remove product from cart")
def test_CART_05():
    pass


@scenario("../features/cart.feature", "CART-06 Empty cart is displayed correctly")
def test_CART_06():
    pass

@then("the selected product should be displayed in the cart")
def selected_product_is_displayed(shared_data):
    shared_data["cart_page"].verifyProduct(shared_data["product"])


@when("the admin adds multiple products to the cart")
def admin_adds_multiple_products(shared_data):
    first_product = shared_data["dashboard_page"].addProductToCart(1)
    second_product = shared_data["dashboard_page"].addProductToCart(2)
    shared_data["products"] = [first_product, second_product]


@then("all selected products should be displayed in the cart")
def all_products_are_displayed(shared_data):
    shared_data["cart_page"].verifyProducts(shared_data["products"])


@then("the correct product name should be displayed")
def correct_product_name_is_displayed(shared_data):
    shared_data["cart_page"].verifyProductName(shared_data["product"])


@then("the correct product price should be displayed")
def correct_product_price_is_displayed(shared_data):
    shared_data["cart_page"].verifyProductPrice(shared_data["product"])


@then("the cart total should equal the sum of the selected products")
def cart_total_is_correct(shared_data):
    shared_data["cart_page"].verifyTotal(shared_data["products"])


@when("the admin removes a product from the cart")
def admin_removes_product(shared_data):
    removed_product = shared_data["products"][0]
    shared_data["cart_page"].removeProduct(removed_product["id"])
    shared_data["removed_product"] = removed_product
    shared_data["remaining_products"] = shared_data["products"][1:]


@then("the removed product should no longer be displayed")
def removed_product_is_not_displayed(shared_data):
    shared_data["cart_page"].verifyProductRemoved(shared_data["removed_product"])


@then("the cart total should be updated")
def cart_total_is_updated(shared_data):
    shared_data["cart_page"].verifyTotal(shared_data["remaining_products"])


@then("the cart should be empty")
def cart_is_empty(shared_data):
    shared_data["cart_page"].verifyCartEmpty()