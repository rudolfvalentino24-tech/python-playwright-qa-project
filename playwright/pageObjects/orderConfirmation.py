from playwright.sync_api import expect
from pageObjects.ordersHistory import OrdersHistoryPage

class OrderConfirmationPage:

    def __init__(self, page):
        self.page = page

    def verifyOrderSuccess(self):

        expect(self.page.get_by_test_id("order-success")).to_have_text("Order Successful")

    def getOrderNumber(self):

        order_text = (self.page.get_by_test_id("order-number").inner_text())
        order_number = (order_text.replace("Order number:", "").strip())
        assert order_number, ("Order number was not generated")
        return order_number

    def openOrderHistory(self):

        self.page.get_by_test_id("view-orders").click()
        return OrdersHistoryPage(self.page)