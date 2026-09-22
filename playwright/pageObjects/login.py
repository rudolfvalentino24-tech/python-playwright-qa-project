from playwright.sync_api import expect
from pageObjects.dashboard import DashboardPage
from pageObjects.ordersHistory import OrdersHistoryPage
from utils.config import storeURL

class LoginPage:
    def __init__(self, page):
        self.page = page

    def navigate(self):
        self.page.goto(storeURL)

    def login(self, userEmail, userPassword):
        self.page.get_by_label("Username").fill(userEmail)
        self.page.get_by_label("Password").fill(userPassword)
        self.page.locator("#termsCheckbox").check()
        self.page.get_by_role("button", name="Login").click()
        dashboardPage = DashboardPage(self.page)

        expect(self.page).to_have_url(f"{storeURL}/store")
        return dashboardPage

    # Submit the login form without assuming that authentication succeeds
    def submitLogin(self, userEmail, userPassword):
        self.page.get_by_label("Username").fill(userEmail)
        self.page.get_by_label("Password").fill(userPassword)
        self.page.locator("#termsCheckbox").check()
        self.page.get_by_role("button", name="Login").click()

    # Verify that the login page is displayed
    def verifyLoginPage(self):
        expect(self.page).to_have_url(f"{storeURL}/")
        expect(self.page.get_by_role("button", name="Login")).to_be_visible()

    # Submit valid credentials without accepting the Terms & Conditions
    def loginWithoutTerms(self, userEmail, userPassword):
        self.page.get_by_label("Username").fill(userEmail)
        self.page.get_by_label("Password").fill(userPassword)
        self.page.get_by_role("button", name="Login").click()

    # Verify that the login attempt was rejected
    def verifyInvalidLogin(self):
        expect(self.page.get_by_test_id("login-error")).to_be_visible()

    # Verify the browser validation message for the required Terms checkbox
    def verifyTermsValidation(self):
        terms_checkbox = self.page.locator("#termsCheckbox")
        expect(terms_checkbox).to_be_focused()
        assert terms_checkbox.evaluate("element => element.validity.valueMissing")
        assert terms_checkbox.evaluate("element => element.validationMessage")

    # Verify that logout removed the authenticated session
    def verifySessionEnded(self):
        self.page.goto(f"{storeURL}/store")
        expect(self.page).to_have_url(f"{storeURL}/")
        expect(self.page.get_by_role("button", name="Login")).to_be_visible()

    # Try to open the protected Store page without being authenticated
    def openProtectedStorePage(self):
        self.page.goto(f"{storeURL}/store")

    def loginAsViewer(self, credentials):
        self.submitLogin(credentials["userEmail"], credentials["userPassword"])
        orders_page = OrdersHistoryPage(self.page)
        orders_page.verifyOrdersLoaded()
        return orders_page

    def openProtectedPage(self, name, order_id=None):
        paths = {"Store": "/store", "Cart": "/cart", "Checkout": "/checkout",
                 "Order History": "/orders", "Order Details": f"/orders/{order_id}"}
        self.page.goto(f"{storeURL}{paths[name]}")

    def verifyRequiredField(self, name):
        field = self.page.get_by_label(name, exact=True)
        expect(field).to_be_focused()
        assert field.evaluate("element => element.validity.valueMissing")
        assert field.evaluate("element => element.validationMessage")
