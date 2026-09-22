from playwright.sync_api import expect
from pageObjects.checkout import CheckoutPage


class CartPage:

    def __init__(self, page):
        self.page = page

    def verifyProduct(self, product):

        cart_item = self.page.get_by_test_id(f"cart-item-{product['id']}")
        expect(cart_item).to_be_visible()
        expect(cart_item).to_contain_text(product["name"])

    def getTotal(self):

        total_text = (self.page.get_by_test_id("cart-total").inner_text())
        return float(total_text.split("€")[1].strip())

    def proceedToCheckout(self):

        self.page.get_by_test_id("checkout-button").click()
        return CheckoutPage(self.page)