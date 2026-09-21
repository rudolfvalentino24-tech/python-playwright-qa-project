from pageObjects.orderDetails import OrderDetailsPage


class OrdersHistoryPage:
    def __init__(self, page):
        self.page = page

    # Verify API-created order exists in UI
    def selectOrder(self, order_id):
        self.page.get_by_test_id(f"view-order-{order_id}").click()
        oderDetailsPage = OrderDetailsPage(self.page)
        return oderDetailsPage