from playwright.sync_api import expect

from pageObjects.orderDetails import OrderDetailsPage


class OrdersHistoryPage:
    def __init__(self, page):
        self.page = page

    def selectOrder(self, order_id):
        # Click View Order for the exact API-created order.
        view_order_button = self.page.get_by_test_id(
            f"view-order-{order_id}"
        )
        expect(view_order_button).to_be_visible()
        view_order_button.click()

        return OrderDetailsPage(self.page, order_id)
