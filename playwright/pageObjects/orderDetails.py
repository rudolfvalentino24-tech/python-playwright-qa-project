from playwright.sync_api import expect
from utils.config import storeURL


class OrderDetailsPage:
    def __init__(self, page, order_id):
        self.page = page
        self.order_id = order_id

    # Verify both the order URL and displayed order number
    def verifyOrderNumber(self):
        expect(self.page).to_have_url(f"{storeURL}/orders/{self.order_id}")
        expect(self.page.get_by_test_id("order-details-number")).to_have_text(self.order_id)

    def verifyProduct(self, product):
        rows = self.page.get_by_test_id("order-details-table").locator("tbody tr")
        row = rows.filter(has=self.page.get_by_role("cell", name=product["name"], exact=True))
        quantity = product.get("quantity", 1)
        expect(row.locator("td")).to_have_text([
            product["name"], str(quantity), f"€{product['price']:.2f}",
            f"€{product['price'] * quantity:.2f}",
        ])

    def verifyProducts(self, products):
        expect(self.page.get_by_test_id("order-details-table").locator("tbody tr")).to_have_count(len(products))
        for product in products:
            self.verifyProduct(product)

    def verifyCustomer(self, customer):
        customer_name = (f"{customer['firstName']} "f"{customer['lastName']}")

        expect(self.page.get_by_text(f"Customer: {customer_name}")).to_be_visible()
        expect(self.page.get_by_text(f"Email: {customer['email']}")).to_be_visible()
        expect(self.page.get_by_text(f"Address: {customer['address']}")).to_be_visible()
        expect(self.page.get_by_text(f"Country: {customer['country']}")).to_be_visible()

    def verifyTotal(self, expected_total):

        expect(self.page.get_by_test_id("order-details-total")).to_have_text(f"Total: €{expected_total:.2f}")

    def deleteOrder(self):
        self.verifyOrderNumber()
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.get_by_test_id("delete-order").click()

    def verifyReadOnly(self):
        self.verifyOrderNumber()
        expect(self.page.get_by_test_id("delete-order")).to_have_count(0)
