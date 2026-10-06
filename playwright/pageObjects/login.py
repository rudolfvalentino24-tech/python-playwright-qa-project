from playwright.sync_api import expect
from pageObjects.dashboard import DashboardPage
from pageObjects.ordersHistory import OrdersHistoryPage
from utils.config import storeURL

class LoginPage:
    def __init__(self, page):
        self.page = page

    def navigate(self):
        # Render free services can show a temporary loading page while waking up.
        self.page.goto(storeURL, wait_until="domcontentloaded", timeout=60000)
        login_button = self.page.get_by_role("button", name="Login")

        try:
            expect(login_button).to_be_visible(timeout=90000)
        except AssertionError:
            # One reload covers the case where Render finished waking but the
            # temporary interstitial did not refresh itself.
            self.page.reload(wait_until="domcontentloaded", timeout=60000)
            expect(login_button).to_be_visible(timeout=30000)

    def login(self, userEmail, userPassword):
        self.page.get_by_label("Username").fill(userEmail)
        self.page.get_by_label("Password", exact=True).fill(userPassword)
        self.page.locator("#termsCheckbox").check()
        self.page.get_by_role("button", name="Login").click()
        dashboardPage = DashboardPage(self.page)

        expect(self.page).to_have_url(f"{storeURL}/store")
        return dashboardPage

    # Submit the login form without assuming that authentication succeeds
    def submitLogin(self, userEmail, userPassword):
        self.page.get_by_label("Username").fill(userEmail)
        self.page.get_by_label("Password", exact=True).fill(userPassword)
        self.page.locator("#termsCheckbox").check()
        self.page.get_by_role("button", name="Login").click()

    # Verify that the login page is displayed
    def verifyLoginPage(self):
        expect(self.page).to_have_url(f"{storeURL}/")
        expect(self.page.get_by_role("button", name="Login")).to_be_visible()

    # Submit valid credentials without accepting the Terms & Conditions
    def loginWithoutTerms(self, userEmail, userPassword):
        self.page.get_by_label("Username").fill(userEmail)
        self.page.get_by_label("Password", exact=True).fill(userPassword)
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

    # Open the Terms & Conditions page from the login form
    def openTermsAndConditions(self):
        self.page.get_by_test_id("terms-link").click()

    # Verify that the Terms & Conditions page is displayed
    def verifyTermsAndConditionsPage(self):
        expect(self.page).to_have_url(f"{storeURL}/terms")
        expect(
            self.page.get_by_role("heading", name="Terms & Conditions")
        ).to_be_visible()

    # Return from Terms & Conditions to the login page
    def returnToLoginPage(self):
        self.page.get_by_test_id("back-to-login").click()
        self.verifyLoginPage()

    def verifyQATrainingWarning(self):
        expect(
            self.page.get_by_text(
                "This is a QA training application. Do not enter real payment information.",
                exact=True,
            )
        ).to_be_visible()

    def enterLoginCredentials(self, userEmail, userPassword):
        # Enter valid login data without submitting the form
        self.page.get_by_label("Username").fill(userEmail)
        self.page.get_by_label("Password", exact=True).fill(userPassword)
        self.page.locator("#termsCheckbox").check()

    def verifyLoginFormNotSubmitted(self):
        # Verify using the visibility toggle did not navigate away from login
        expect(self.page).to_have_url(f"{storeURL}/")

    def submitLoginForm(self):
        # Submit credentials that were already entered in the login form
        self.page.get_by_role("button", name="Login").click()
        return DashboardPage(self.page)

    def enterPassword(self, password):
        self.page.get_by_label("Password",exact=True).fill(password)

    def verifyPasswordMasked(self):
        # Verify the password field is using the browser's hidden password mode
        password_field = self.page.get_by_label("Password", exact=True)
        expect(password_field).to_have_attribute("type", "password")

    def verifyPasswordVisible(self):
        # Verify the password field is visible
        password_field = self.page.get_by_label("Password", exact=True)
        expect(password_field).to_have_attribute("type", "text")

    def clickPasswordVisibilityToggle(self):
            self.page.get_by_test_id("password-visibility-toggle").click()

    def verifyPasswordValue(self, password):
        # Verify toggling visibility does not modify the entered password
        password_field = self.page.get_by_label("Password", exact=True)
        expect(password_field).to_have_value(password)

    def navigateToPasswordVisibilityToggleUsingKeyboard(self):
        self.page.get_by_label("Password", exact=True).press("Tab")

    def verifyPasswordVisibilityToggleFocused(self):
        toggle = self.page.get_by_test_id("password-visibility-toggle")
        expect(toggle).to_be_focused()

    def activatePasswordVisibilityToggleUsingKeyboard(self):
        toggle = self.page.get_by_test_id("password-visibility-toggle")
        toggle.press("Enter")

    def verifyPasswordVisibilityToggleAccessibleLabel(self, label):
        # Verify the visibility control exposes the expected accessible name
        toggle = self.page.get_by_test_id("password-visibility-toggle")
        expect(toggle).to_have_accessible_name(label)

    def reloadLoginPage(self):
        # Reload the login page to verify visibility state does not persist
        self.page.reload(wait_until="domcontentloaded")
        self.verifyLoginPage()

    def leaveAndReturnToLoginPage(self):
        # Leave the login page and return through the existing Terms navigation flow
        self.openTermsAndConditions()
        self.returnToLoginPage()
