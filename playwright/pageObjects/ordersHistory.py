from playwright.sync_api import expect
from utils.config import storeURL

from pageObjects.orderDetails import OrderDetailsPage


class OrdersHistoryPage:
    def __init__(self, page):
        self.page = page

    def selectOrder(self, order_id):
        # Click View Order for the exact order created by the test.
        view_order_button = self.page.get_by_test_id(
            f"view-order-{order_id}"
        )
        expect(view_order_button).to_be_visible()
        view_order_button.click()

        return OrderDetailsPage(self.page, order_id)

    def verifyOrderExists(self, order_id):

        expect(self.page.get_by_test_id(f"view-order-{order_id}")).to_be_visible()

    def verifyOrdersLoaded(self):
        expect(self.page).to_have_url(f"{storeURL}/orders")
        # Both a populated history and a successfully loaded empty history are valid.
        expect(self.page.locator(
            '[data-testid="orders-count"], [data-testid="no-orders"]'
        )).to_be_visible()
        expect(self.page.get_by_test_id("orders-error")).to_have_count(0)

    def deleteOrder(self, order_id):
        self.verifyOrderExists(order_id)
        self.page.once("dialog", lambda dialog: dialog.accept())
        self.page.get_by_test_id(f"delete-order-{order_id}").click()

    def verifyOrderRemoved(self, order_id):
        self.verifyOrdersLoaded()
        expect(self.page.get_by_test_id(f"order-{order_id}")).to_have_count(0)
        expect(self.page.get_by_test_id(f"view-order-{order_id}")).to_have_count(0)

    def refresh(self):
        self.page.reload()
        self.verifyOrdersLoaded()

    def open(self):
        self.page.goto(f"{storeURL}/orders")
        self.verifyOrdersLoaded()

    def verifyReadOnly(self):
        self.verifyOrdersLoaded()
        expect(self.page.locator('[data-testid^="delete-order-"]')).to_have_count(0)
        expect(self.page.get_by_test_id("orders-back-to-store")).to_have_count(0)

    def logout(self):
        self.page.get_by_test_id("orders-logout-button").click()
