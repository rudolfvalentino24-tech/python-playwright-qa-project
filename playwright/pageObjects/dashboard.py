from pageObjects.ordersHistory import OrdersHistoryPage


class DashboardPage:
    def __init__(self, page):
        self.page = page

    def selectOrdersNaviLink(self):
        # Open order history.
        self.page.get_by_test_id("orders-link").click()
        return OrdersHistoryPage(self.page)

    # Backward-compatible alias for older tests while the typo is being removed.
    def selectOerdersNaviLink(self):
        return self.selectOrdersNaviLink()
