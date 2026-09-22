from playwright.sync_api import expect
from pageObjects.checkout import CheckoutPage


class CartPage:

    def __init__(self, page):
        self.page = page

    # Verify that a selected product is displayed in the cart
    def verifyProduct(self, product):
        cart_item = self.page.get_by_test_id(f"cart-item-{product['id']}")
        expect(cart_item).to_be_visible()
        expect(cart_item).to_contain_text(product["name"])

    # Verify that all selected products are displayed in the cart
    def verifyProducts(self, products):
        for product in products:
            self.verifyProduct(product)

    # Verify the correct product name
    def verifyProductName(self, product):
        cart_item = self.page.get_by_test_id(f"cart-item-{product['id']}")
        expect(cart_item).to_contain_text(product["name"])

    # Verify the correct product price
    def verifyProductPrice(self, product):
        cart_item = self.page.get_by_test_id(f"cart-item-{product['id']}")
        expect(cart_item).to_contain_text(f"€{product['price']:.2f}")

    # Return the displayed cart total as a number
    def getTotal(self):
        total_text = self.page.get_by_test_id("cart-total").inner_text()
        return float(total_text.replace("Total: €", "").strip())

    # Verify that the displayed total equals the sum of the products
    def verifyTotal(self, products):
        expected_total = sum(product["price"] for product in products)
        expect(self.page.get_by_test_id("cart-total")).to_have_text(f"Total: €{expected_total:.2f}")

    # Remove a product from the cart
    def removeProduct(self, product_id):
        self.page.get_by_test_id(f"remove-product-{product_id}").click()

    # Verify that a removed product is no longer displayed
    def verifyProductRemoved(self, product):
        expect(self.page.get_by_test_id(f"cart-item-{product['id']}")).not_to_be_visible()

    # Verify that the cart contains no products
    def verifyCartEmpty(self):
        expect(self.page.get_by_role("heading", name="Your cart is empty")).to_be_visible()

    # Open checkout and return the CheckoutPage object
    def proceedToCheckout(self):
        self.page.get_by_test_id("checkout-button").click()
        return CheckoutPage(self.page)