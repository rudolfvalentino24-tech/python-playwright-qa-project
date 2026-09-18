import time
from playwright.sync_api import Page, Playwright,  expect


def test_UIChecks(page: Page):
    page.goto("http://127.0.0.1:3001")
    page.get_by_label("Username").fill("tester")
    page.get_by_label("password").fill("password123")
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()
    expect(page.get_by_placeholder("Write a short description")).to_be_visible()
    page.get_by_placeholder("Write a short description").fill("Newtwo")
    expect(page.locator("textarea")).to_have_value("Newtwo")

def test_alertBoxes(page: Page):
    page.goto("http://127.0.0.1:3001")
    page.get_by_label("Username").fill("tester")
    page.get_by_label("password").fill("password123")
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()

    #alert Boxes
    page.on("dialog", lambda dialog:dialog.accept())
    page.get_by_role("button", name="JavaScript Alert").click()
    time.sleep(5)

def test_frames(page: Page):
    page.goto("http://127.0.0.1:3001")
    page.get_by_label("Username").fill("tester")
    page.get_by_label("password").fill("password123")
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()

    #frames
    page.on("dialog", lambda dialog: dialog.accept())
    pageFrame = page.frame_locator("#dialogFrame")
    pageFrame.get_by_role("button", name="JavaScript Alert").click()

def test_tables(page: Page):
    page.goto("http://127.0.0.1:3001")

    page.get_by_label("Username").fill("tester")
    page.get_by_label("password").fill("password123")
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()

    # Find Role column
    for index in range(page.locator("th").count()):
        if page.locator("th").nth(index).filter(has_text="Role").count() > 0:
            roleColValue = index
            print(f"The column is {roleColValue}")
            break

    # Sort Name descending, matching your screenshot
    page.get_by_role("button", name="Name ↕").click()

    # Hana is now on page 1
    nameRow = page.locator("tr").filter(has_text="Hana")

    expect(
        nameRow.locator("td").nth(roleColValue)
    ).to_have_text("QA Engineer")

def test_mouseHover(page: Page):
    page.goto("http://127.0.0.1:3001")
    page.get_by_label("Username").fill("tester")
    page.get_by_label("Password").fill("password123")
    page.locator("#termsCheckbox").check()
    page.get_by_role("button", name="Login").click()

    page.locator("#tooltipBtn").hover()
    page.get_by_role("tooltip").click()

