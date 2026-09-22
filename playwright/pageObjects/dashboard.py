from pageObjects.ordersHistory import OrdersHistoryPage
from playwright.sync_api import expect
from pageObjects.cart import CartPage
from utils.config import storeURL

class DashboardPage:
    def __init__(self, page):
        self.page = page

    def addProductToCart(self, product_id):

        product_name = self.page.get_by_test_id(f"product-name-{product_id}")
        product_price = self.page.get_by_test_id(f"price-{product_id}")
        expect(product_name).to_be_visible()
        expect(product_price).to_be_visible()

        product = {
            "id": product_id,
            "name": product_name.inner_text(),
            "price": float(
                product_price.inner_text()
                .replace("€", "")
                .strip()
            )
        }

        self.page.get_by_test_id(f"add-product-{product_id}").click()
        expect(self.page.get_by_test_id("cart-link")).to_contain_text("Cart (1)")

        return product

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
