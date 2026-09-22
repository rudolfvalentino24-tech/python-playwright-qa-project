from playwright.sync_api import expect

from utils.config import storeURL


class OrderDetailsPage:
    def __init__(self, page, order_id):
        self.page = page
        self.order_id = order_id

    def verifyOrderNumber(self):
        # Verify both navigation and the order number shown on the details page.
        expect(self.page).to_have_url(f"{storeURL}/orders/{self.order_id}")
        expect(self.page.get_by_test_id("order-details-number")).to_have_text(self.order_id)

    def verifyProduct(self, product):

        expect(self.page.get_by_test_id("order-details-table")).to_contain_text(product["name"])

    def verifyCustomer(self, customer):
        customer_name = (f"{customer['firstName']} "f"{customer['lastName']}")

        expect(self.page.get_by_text(f"Customer: {customer_name}")).to_be_visible()
        expect(self.page.get_by_text(f"Email: {customer['email']}")).to_be_visible()
        expect(self.page.get_by_text(f"Address: {customer['address']}")).to_be_visible()
        expect(self.page.get_by_text(f"Country: {customer['country']}")).to_be_visible()

    def verifyTotal(self, expected_total):

        expect(self.page.get_by_test_id("order-details-total")).to_contain_text(f"€{expected_total:.2f}")
