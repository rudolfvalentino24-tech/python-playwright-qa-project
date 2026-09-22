from pageObjects.orderConfirmation import OrderConfirmationPage

class CheckoutPage:

    def __init__(self, page):
        self.page = page

    def enterCheckoutInformation(
        self,
        customer,
        payment
    ):

        self.page.get_by_test_id("checkout-first-name").fill(customer["firstName"])
        self.page.get_by_test_id("checkout-last-name").fill(customer["lastName"])
        self.page.get_by_test_id("checkout-email").fill(customer["email"])
        self.page.get_by_test_id("checkout-address").fill(customer["address"])
        self.page.get_by_test_id("checkout-country").select_option(customer["country"])
        self.page.get_by_test_id("card-name").fill(payment["cardName"])
        self.page.get_by_test_id("card-number").fill(payment["cardNumber"])
        self.page.get_by_test_id("card-expiry").fill(payment["expiry"])
        self.page.get_by_test_id("card-cvv").fill(payment["cvv"])
        self.page.get_by_test_id("confirm-order-checkbox").check()

    def placeOrder(self):

        self.page.get_by_test_id("place-order-button").click()
        return OrderConfirmationPage(self.page)