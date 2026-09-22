from pageObjects.ordersHistory import OrdersHistoryPage
from playwright.sync_api import expect
from pageObjects.cart import CartPage
from utils.config import storeURL

class DashboardPage:
    def __init__(self, page):
        self.page = page

    # Add a product to the cart and return its details
    def addProductToCart(self, product_id):
        product_name = self.page.get_by_test_id(f"product-name-{product_id}").inner_text()
        product_price = self.page.get_by_test_id(f"price-{product_id}").inner_text()

        self.page.get_by_test_id(f"add-product-{product_id}").click()

        return {
            "id": product_id,
            "name": product_name,
            "price": float(product_price.replace("€", "").strip())
        }

    def openCart(self):

        self.page.get_by_test_id("cart-link").click()

        return CartPage(self.page)

    def selectOrdersNaviLink(self):
        # Open order history.
        self.page.get_by_test_id("orders-link").click()
        return OrdersHistoryPage(self.page)

    # Verify that login succeeded by checking that the admin was redirected to the Store page
    def verifyLoginSuccessful(self):
        expect(self.page).to_have_url(f"{storeURL}/store")

    # Verify that the main Store content is displayed
    def verifyStorePage(self):
        expect(self.page.get_by_test_id("cart-link")).to_be_visible()
        expect(self.page.get_by_test_id("orders-link")).to_be_visible()

    def logout(self):
        self.page.get_by_test_id("logout-button").click()

    # Verify that products and their Add to Cart buttons are displayed
    def verifyProductsDisplayed(self):
        product_names = self.page.locator("[data-testid^='product-name-']")
        add_buttons = self.page.locator("[data-testid^='add-product-']")

        expect(product_names.first).to_be_visible()
        expect(add_buttons.first).to_be_visible()

        assert product_names.count() > 0
        assert product_names.count() == add_buttons.count()

    # Verify that every product has a visible product name
    def verifyProductNames(self, products):
        product_names = self.page.locator("[data-testid^='product-name-']")

        assert product_names.count() > 0

        for index in range(product_names.count()):
            expect(product_names.nth(index)).to_be_visible()
        expect(product_names).to_have_count(len(products))
        for product in products:
            expect(self.page.get_by_test_id(f"product-name-{product['id']}")).to_have_text(product["name"])

    # Verify that every product has a visible price
    def verifyProductPrices(self, products):
        product_prices = self.page.locator("[data-testid^='price-']")

        assert product_prices.count() > 0

        for index in range(product_prices.count()):
            expect(product_prices.nth(index)).to_be_visible()
        for product in products:
            expect(self.page.get_by_test_id(f"price-{product['id']}")).to_have_text(f"€{product['price']:.2f}")

    # Verify that every expected product has an Add to Cart button
    def verifyAddToCartButtons(self, products):
        add_buttons = self.page.locator("[data-testid^='add-product-']")
        expect(add_buttons).to_have_count(len(products))

        for product in products:
            expect(self.page.get_by_test_id(f"add-product-{product['id']}")).to_be_visible()
