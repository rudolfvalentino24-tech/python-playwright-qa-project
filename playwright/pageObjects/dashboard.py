from pageObjects.ordersHistory import OrdersHistoryPage

class DashboardPage:
    def __init__(self, page):
        self.page = page

    def selectOerdersNaviLink(self):
        # Open order history
        self.page.get_by_test_id("orders-link").click()
        ordersHistoryPage = OrdersHistoryPage(self.page)
        return ordersHistoryPage