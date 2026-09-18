from playwright.sync_api import Page, Playwright,  expect
from utils.config import storeURL, playgroundURL

def test_UIValidationDynamincScript(page: Page):
    # Wireless Mouse, Playwright T-Shirt -> verify 2 items
    page.goto(storeURL)
    mouse = page.locator(".product").filter(has_text="Wireless Mouse")
    mouse.get_by_role("button", name="Add to Cart").click()
    tshirt = page.locator(".product").filter(has_text="Playwright T-Shirt") #CSS class and filter visible text
    tshirt.get_by_role("button").click()
    cart_button = page.get_by_test_id("cart-link")
    expect(cart_button).to_be_visible()
    expect(cart_button).to_have_text("Cart (2)")
    cart_button.click()

    mouse_item = page.locator(".cart-item").filter(has_text="Wireless Mouse")
    tshirt_item = page.locator(".cart-item").filter(has_text="Playwright T-Shirt")

    expect(mouse_item.locator('input[name="quantity"]')).to_have_value("1")
    expect(tshirt_item.locator('input[name="quantity"]')).to_have_value("1")

def test_childWindowHandle(page:Page):
    page.goto(playgroundURL)
    page.get_by_label("Username").fill("tester")
    page.get_by_label("password").fill("password123")
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()

    with page.expect_popup() as newPage_info:
        page.locator(".popup-banner").click()
        childPage = newPage_info.value
        childPage.locator("")