from playwright.sync_api import Page, expect


def test_orders_user_restricted_to_orders(page: Page):

    # Open login page
    page.goto("http://127.0.0.1:3002")

    # Login as restricted user
    page.get_by_label("Username").fill("ordersuser")
    page.get_by_label("Password").fill("orders123")
    page.locator("#termsCheckbox").check()

    page.get_by_role(
        "button",
        name="Login"
    ).click()

    # Restricted user should be sent to Orders
    expect(page).to_have_url(
        "http://127.0.0.1:3002/orders"
    )

    # Verify Orders page is accessible
    expect(
        page.get_by_role("heading", name="Order History")
    ).to_be_visible()

    # Try to access the Store directly
    page.goto("http://127.0.0.1:3002/store")

    # User should be redirected back to Orders
    expect(page).to_have_url(
        "http://127.0.0.1:3002/orders"
    )