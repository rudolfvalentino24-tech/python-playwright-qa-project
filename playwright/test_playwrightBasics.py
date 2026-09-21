import os

from playwright.sync_api import Page, Playwright

from utils.config import playgroundURL


def _jenkins_headless():
    return os.getenv("JENKINS_URL") is not None


def test_playwrightBasics(playwright: Playwright):
    browser = playwright.chromium.launch(headless=_jenkins_headless())
    context = browser.new_context()

    try:
        page = context.new_page()
        page.goto(playgroundURL)
    finally:
        context.close()
        browser.close()


# CHROMIUM HEADLESS MODE (pytest-playwright page fixture)
def test_playwrightShotCut(page: Page):
    page.goto(playgroundURL)


def test_coreLocators(page: Page, admin_credentials):
    page.goto(playgroundURL)
    page.get_by_role("link", name="Terms & Conditions").click()
    page.go_back()
    page.get_by_label("Username").fill(admin_credentials["userEmail"])
    page.get_by_label("password").fill(admin_credentials["userPassword"])
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()


def test_firefoxBrowser(playwright: Playwright, admin_credentials):
    firefox_browser = playwright.firefox.launch(headless=_jenkins_headless())

    try:
        page = firefox_browser.new_page()
        page.goto(playgroundURL)
        page.get_by_role("link", name="Terms & Conditions").click()
        page.go_back()
        page.get_by_label("Username").fill(admin_credentials["userEmail"])
        page.get_by_label("password").fill(admin_credentials["userPassword"])
        page.locator("#termsCheckbox").check()
        page.get_by_role("button", name="Login").click()
    finally:
        firefox_browser.close()
