from playwright.sync_api import expect

from utils.config import storeURL


class OrderDetailsPage:
    def __init__(self, page, order_id):
        self.page = page
        self.order_id = order_id

    def verifyOrderMessage(self):
        # Verify both navigation and the order number shown on the details page.
        expect(self.page).to_have_url(
            f"{storeURL}/orders/{self.order_id}"
        )
        expect(
            self.page.get_by_test_id("order-details-number")
        ).to_have_text(self.order_id)
