from playwright.sync_api import Page, Playwright,  expect
from utils.config import playgroundURL

def test_playwrightBasics(playwright):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(playgroundURL)

#CHROMIUM HEADLESS MODE
def test_playwrightShotCut(page : Page):
    page.goto(playgroundURL)

def test_coreLocators(page : Page):
    page.goto(playgroundURL)
    page.get_by_role("link", name="Terms & Conditions").click()
    page.go_back()
    page.get_by_label("Username").fill("tester")
    page.get_by_label("password").fill("password13")
    #page.get_by_text("Login").click()
    #page.get_by_test_id("login-button")
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()
    expect(page.get_by_text("Invalid username or password.")).to_be_visible()

def test_firefoxBrowser(playwright : Playwright):
    firefoxBrowser = playwright.firefox.launch(headless=False)
    page = firefoxBrowser.new_page()
    page.goto(playgroundURL)
    page.get_by_role("link", name="Terms & Conditions").click()
    page.go_back()
    page.get_by_label("Username").fill("tester")
    page.get_by_label("password").fill("password13")
    #page.get_by_text("Login").click()
    #page.get_by_test_id("login-button")
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()
    expect(page.get_by_text("Invalid username or password.")).to_be_visible()

