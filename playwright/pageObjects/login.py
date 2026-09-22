from playwright.sync_api import expect
from pageObjects.dashboard import DashboardPage
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
        validation_message = terms_checkbox.evaluate("element => element.validationMessage")
        assert validation_message == "Please check this box if you want to proceed."

    # Verify that logout removed the authenticated session
    def verifySessionEnded(self):
        self.page.goto(f"{storeURL}/store")
        expect(self.page).to_have_url(f"{storeURL}/")
        expect(self.page.get_by_role("button", name="Login")).to_be_visible()