from pytest_bdd import scenario, then


@scenario("../features/store.feature", "STORE-01 Store page loads after admin login")
def test_STORE_01():
    pass

@scenario("../features/store.feature", "STORE-02 Products are displayed")
def test_STORE_02():
    pass

@scenario("../features/store.feature", "STORE-03 Product information is displayed correctly")
def test_STORE_03():
    pass

@then("the products should be displayed")
def products_are_displayed(shared_data):
    shared_data["dashboard_page"].verifyProductsDisplayed()

@then("each product should display its name")
def product_names_are_displayed(shared_data, products):
    shared_data["dashboard_page"].verifyProductNames(products)


@then("each product should display its price")
def product_prices_are_displayed(shared_data, products):
    shared_data["dashboard_page"].verifyProductPrices(products)


@then("each product should have an Add to Cart button")
def add_to_cart_buttons_are_displayed(shared_data, products):
    shared_data["dashboard_page"].verifyAddToCartButtons(products)
