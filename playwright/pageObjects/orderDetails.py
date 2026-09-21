from playwright.sync_api import expect


class OrderDetailsPage:
    def __init__(self, page):
        self.page = page

    def verifyOrderMessage(self):
        expect(self.page.get_by_test_id("order-success"))