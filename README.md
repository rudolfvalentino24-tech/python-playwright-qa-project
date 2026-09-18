# Python Playwright QA Project

A hands-on QA automation project built with **Python**, **Playwright**, **Pytest**, and **Flask**.

The project contains local test applications and automated tests for UI testing, API testing, authentication, authorization, network interception, token handling, and end-to-end scenarios.

---

## Project Goals

This project is used to practice and demonstrate:

- UI automation with Playwright
- API testing with Playwright
- End-to-end testing
- Network interception and mocked API responses
- Authentication with Bearer tokens
- Token expiration
- Role-based authorization
- Session and local storage
- Cart and checkout flows
- Order creation and order history
- Pytest test structure and assertions

---

## Project Structure

```text
PythonProject/
│
├── .gitignore
├── README.md
├── FirstDemo.py
├── main.py
│
├── playwright/
│   ├── utils/
│   │   └── apiBase.py
│   ├── test_codegen.py
│   ├── test_Network.py
│   ├── test_playwrightBasics.py
│   ├── test_UIValidations.py
│   ├── test_UIValidations_1.py
│   └── test_web_api.py
│
├── pytestDir/
│   ├── conftest.py
│   ├── test_PytestValidation.py
│   └── test_PytestValidation2.py
│
├── python_playwright_runner/
│   ├── app.py
│   ├── requirements.txt
│   ├── README.txt
│   └── tests/
│
└── qa_testing_playground/
    ├── qa_playground.py
    ├── store.py
    ├── requirements.txt
    └── README.txt
```

---

## Technologies

- Python
- Playwright
- Pytest
- Flask
- HTML / CSS / JavaScript
- Git
- GitHub

---

## Installation

Create and activate a virtual environment if needed.

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the main dependencies:

```powershell
pip install flask pytest playwright pytest-playwright
```

Install the Playwright browsers:

```powershell
playwright install
```

---

# Local Test Applications

## 1. QA Testing Playground

Start the QA Playground:

```powershell
cd C:\Users\rudol\PycharmProjects\PythonProject\qa_testing_playground
python qa_playground.py
```

Open:

```text
http://127.0.0.1:3001
```

The playground contains examples for login, forms, checkboxes, tabs, accordion, modal dialogs, toast messages, dynamic elements, browser dialogs, iframes, popups, tables, sorting, pagination, drag and drop, keyboard events, and API testing.

---

## 2. QA Test Store

Start the Store:

```powershell
cd C:\Users\rudol\PycharmProjects\PythonProject\qa_testing_playground
python store.py
```

Open:

```text
http://127.0.0.1:3002
```

The Store contains:

- Login
- Bearer-token authentication
- 30-minute token expiration
- Role-based authorization
- Products
- Shopping cart
- Quantity updates
- Checkout
- Order creation
- Order history
- API order creation
- Network interception practice

---

## 3. Python Playwright Runner

Start the runner:

```powershell
cd C:\Users\rudol\PycharmProjects\PythonProject\python_playwright_runner
python app.py
```

Open:

```text
http://127.0.0.1:3000
```

---

# Demo Users

## Admin

```text
Username: tester
Password: password123
Role: admin
```

The admin can access the Store, Cart, Checkout, Orders, GET order API, and POST order API.

## Orders User

```text
Username: ordersuser
Password: orders123
Role: orders_viewer
```

The restricted user can access the Orders page and GET orders API.

The restricted user cannot access the Store, Cart, Checkout, or POST order API.

If the restricted user manually tries to open:

```text
http://127.0.0.1:3002/store
```

the application redirects the user back to:

```text
http://127.0.0.1:3002/orders
```

---

# Bearer Token Authentication

The Store login returns JSON containing a Bearer token.

Example:

```json
{
  "message": "Login successful",
  "username": "tester",
  "role": "admin",
  "token": "generated-token",
  "token_type": "Bearer"
}
```

The token is sent to protected API endpoints using:

```http
Authorization: Bearer <token>
```

Tokens expire after 30 minutes.

---

# API Endpoints

## Login

```text
POST /login
```

Returns username, role, and Bearer token.

## Current User

```text
GET /api/user
```

Requires:

```http
Authorization: Bearer <token>
```

## Get Orders

```text
GET /api/orders
```

Requires a valid Bearer token.

Both the admin and the orders viewer can read orders.

## Create Order

```text
POST /api/orders
```

Requires:

```http
Authorization: Bearer <token>
Content-Type: application/json
```

Admin access is required.

Example request body:

```json
{
  "firstName": "test",
  "lastName": "test",
  "email": "test@example.com",
  "address": "Test Address",
  "country": "AT",
  "items": [
    {
      "productId": 1,
      "quantity": 1
    },
    {
      "productId": 6,
      "quantity": 1
    }
  ]
}
```

Example response:

```json
{
  "message": "Order created successfully",
  "orderId": "TEST-1234567890",
  "username": "tester",
  "total": 54.98
}
```

---

# Example E2E API + UI Test

The test can:

1. Log in through the API.
2. Receive a Bearer token.
3. Create an order through `POST /api/orders`.
4. Receive the generated `orderId`.
5. Open the Store UI.
6. Navigate to the Orders page.
7. Verify that the same order ID appears in the UI.

Example:

```python
order_id = api_utils.createOrder(playwright)

page.get_by_test_id("orders-link").click()

expect(
    page.get_by_text(order_id, exact=True)
).to_be_visible()
```

---

# Network Interception

The Orders page loads order data from:

```text
GET /api/orders
```

Playwright can intercept this request and return a fake response.

Example:

```python
fakePayloadOrderResponse = {
    "data": [],
    "message": "No orders yet"
}


def intercept_response(route):
    route.fulfill(
        json=fakePayloadOrderResponse
    )


page.route(
    "**/api/orders",
    intercept_response
)
```

Then verify the mocked response in the UI:

```python
expect(
    page.get_by_test_id("no-orders-heading")
).to_have_text("No orders yet")
```

---

# Example Authorization Test

```python
from playwright.sync_api import Page, expect


def test_orders_user_restricted_to_orders(page: Page):

    page.goto("http://127.0.0.1:3002")

    page.get_by_label("Username").fill("ordersuser")
    page.get_by_label("Password").fill("orders123")
    page.locator("#termsCheckbox").check()

    page.get_by_role(
        "button",
        name="Login"
    ).click()

    expect(page).to_have_url(
        "http://127.0.0.1:3002/orders"
    )

    page.goto(
        "http://127.0.0.1:3002/store"
    )

    expect(page).to_have_url(
        "http://127.0.0.1:3002/orders"
    )
```

---

# Running Tests

Run all tests:

```powershell
pytest
```

Run a specific test file:

```powershell
pytest playwright/test_Network.py
```

Run one specific test:

```powershell
pytest playwright/test_Network.py::test_Network
```

Show printed output:

```powershell
pytest -s
```

Run with more detail:

```powershell
pytest -v
```

---

# Useful Playwright Commands

Install browsers:

```powershell
playwright install
```

Generate Playwright code:

```powershell
playwright codegen http://127.0.0.1:3002
```

---

# Git Workflow

After making changes:

```powershell
git status
git add .
git commit -m "Describe your changes"
git push
```

Example:

```powershell
git add .
git commit -m "Add role based authorization tests"
git push
```

---

# Important

This project is a **QA training project**.

The usernames, passwords, tokens, products, orders, and payment information are all test data.

Do not use real passwords, API keys, secrets, or payment information in this repository.

---

## Repository

GitHub:

```text
https://github.com/rudolfvalentino24-tech/python-playwright-qa-project
```
