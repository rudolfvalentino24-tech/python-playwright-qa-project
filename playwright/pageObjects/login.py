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

        expect(self.page).to_have_url(
            f"{storeURL}/store"
        )
        return dashboardPage