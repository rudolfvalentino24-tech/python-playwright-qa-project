import re

from playwright.sync_api import expect
from pageObjects.orderConfirmation import OrderConfirmationPage

class CheckoutPage:

    FIELD_TEST_IDS = {
        "first name": "checkout-first-name",
        "last name": "checkout-last-name",
        "email": "checkout-email",
        "address": "checkout-address",
        "country": "checkout-country",
        "cardholder name": "card-name",
        "card number": "card-number",
        "expiry": "card-expiry",
        "CVV": "card-cvv",
        "order confirmation": "confirm-order-checkbox",
    }

    def __init__(self, page):
        self.page = page

    def verifyCheckoutPage(self):
        expect(self.page).to_have_url(re.compile(r"/checkout/?$"))
        expect(self.page.get_by_role("heading", name="Checkout", exact=True)).to_be_visible()
        expect(self.page.get_by_test_id("place-order-button")).to_be_visible()

    def verifyTotal(self, expected_total):
        expect(self.page.get_by_test_id("checkout-total")).to_have_text(
            f"Total: €{expected_total:.2f}"
        )

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

    def clearField(self, field_name):
        field = self.page.get_by_test_id(self.FIELD_TEST_IDS[field_name])
        if field_name == "country":
            field.select_option("")
        else:
            field.fill("")

    def setEmail(self, email):
        self.page.get_by_test_id("checkout-email").fill(email)

    def uncheckOrderConfirmation(self):
        self.page.get_by_test_id("confirm-order-checkbox").uncheck()

    def submitOrder(self):
        self.page.get_by_test_id("place-order-button").click()

    def verifySubmissionBlocked(self):
        self.verifyCheckoutPage()
        expect(self.page.get_by_test_id("order-success")).to_have_count(0)

    def verifyFieldValidation(self, field_name, validity_reason):
        field = self.page.get_by_test_id(self.FIELD_TEST_IDS[field_name])
        # Only the deliberately invalid field should prevent submission.
        expect(self.page.locator("form :invalid")).to_have_count(1)
        expect(field).to_be_focused()
        assert field.evaluate(
            "(element, reason) => element.validity[reason]", validity_reason
        ), f"Expected {validity_reason} validation for {field_name}"
        # Native validation messages vary by browser and language.
        assert field.evaluate("element => element.validationMessage"), (
            f"Expected a validation message for {field_name}"
        )

    def placeOrder(self):
        self.submitOrder()
        return OrderConfirmationPage(self.page)
