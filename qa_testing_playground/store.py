from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from datetime import timedelta
import os
import secrets
import time
# -------------------------
# DATA
# -------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "qa-store-secret-key")
app.permanent_session_lifetime = timedelta(days=30)

USERS = {
    "tester": {
        "password": "password123",
        "role": "admin"
    },
    "admin2": {
        "password": "admin123",
        "role": "admin"
    },
    "ordersuser": {
        "password": "orders123",
        "role": "orders_viewer"
    }
}

PRODUCTS = [
    {"id": 1, "name": "Wireless Mouse", "price": 29.99, "category": "Electronics"},
    {"id": 2, "name": "Mechanical Keyboard", "price": 89.99, "category": "Electronics"},
    {"id": 3, "name": "USB-C Hub", "price": 49.99, "category": "Electronics"},
    {"id": 4, "name": "Laptop Stand", "price": 39.99, "category": "Office"},
    {"id": 5, "name": "QA Testing Mug", "price": 14.99, "category": "Accessories"},
    {"id": 6, "name": "Playwright T-Shirt", "price": 24.99, "category": "Clothing"},
]

# Order history and Bearer tokens are kept in memory while the Flask server is running.
ORDER_HISTORY = {}

# Bearer tokens expire after 30 minutes.
TOKEN_EXPIRY_SECONDS = 30 * 60

# TOKENS[token] = {
#     "username": "...",
#     "role": "...",
#     "expires_at": <unix timestamp>
# }
TOKENS = {}

# ============================================================
# HTML TEMPLATE: LOGIN PAGE
# Edit the Store login page below.
# ============================================================
LOGIN_HTML = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QA Test Store - Login</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#172033;background:#f5f7fb}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px}
.card{width:min(420px,100%);background:#fff;border:1px solid #dce2ec;border-radius:16px;padding:28px}
h1{margin:0 0 8px} p{color:#5f6b7a}
label{display:block;font-weight:650;margin-top:14px}
input{width:100%;padding:11px 12px;margin-top:6px;border:1px solid #b8c1cf;border-radius:9px;font-size:16px}
button{width:100%;margin-top:18px;padding:12px;border:0;border-radius:9px;background:#2457d6;color:#fff;font-weight:750;cursor:pointer}
.error{display:none;margin-top:12px;padding:10px;background:#fff0f0;color:#9b1c1c;border-radius:8px}
</style>
</head>
<body>
<main class="card">
  <h1 data-testid="login-title">QA Test Store</h1>
  <p>Sign in to enter the store.</p>

  <form id="loginForm" method="post" action="/login" data-testid="login-form">
    <label for="username">Username</label>
    <input id="username" name="username" autocomplete="username" required data-testid="username-input">

    <label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required data-testid="password-input">

    <label style="display:flex;align-items:center;gap:8px;font-weight:500">
      <input id="remember" name="remember" type="checkbox" style="width:auto;margin:0" data-testid="remember-checkbox">
      Remember me
    </label>

    <label style="display:flex;align-items:center;gap:8px;font-weight:500">
      <input id="termsCheckbox" name="terms" type="checkbox" required style="width:auto;margin:0" data-testid="terms-checkbox">
      <span>I accept the <a href="/terms" data-testid="terms-link">Terms & Conditions</a></span>
    </label>

    <button type="submit" data-testid="login-button">Login</button>
  </form>

  <div id="loginError" class="error" role="alert" data-testid="login-error"></div>

</main>

<script>
document.getElementById("loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();

  const form = event.currentTarget;
  if (!form.reportValidity()) return;

  const formData = new FormData(form);

  const response = await fetch("/login", {
    method: "POST",
    body: formData
  });

  const data = await response.json();

  if (response.ok) {
    localStorage.setItem("authToken", data.token);
    localStorage.setItem("username", data.username);
    localStorage.setItem("role", data.role);

    if (data.role === "admin") {
      window.location.href = "/store";
    } else {
      window.location.href = "/orders";
    }
  } else {
    const error = document.getElementById("loginError");
    error.textContent = data.error || "Login failed";
    error.style.display = "block";
  }
});
</script>
</body>
</html>
"""

# ============================================================
# HTML TEMPLATE: TERMS & CONDITIONS PAGE
# ============================================================
TERMS_HTML = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Terms</title>
<style>body{font-family:system-ui;padding:40px;background:#f5f7fb;color:#172033}.card{max-width:760px;margin:auto;background:white;border:1px solid #dce2ec;border-radius:14px;padding:24px}a{display:inline-block;margin-top:20px}</style>
</head><body><main class="card">
<h1>Terms & Conditions</h1>
<p>This is a QA training application. Do not enter real payment information.</p>
<p>All products, orders and payment details are fictional and exist only for testing.</p>
<a href="/" data-testid="back-to-login">← Back to Login</a>
</main></body></html>
"""

# ============================================================
# HTML TEMPLATE: MAIN STORE / PRODUCTS PAGE
# ============================================================
STORE_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QA Test Store</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#172033;background:#f5f7fb}
*{box-sizing:border-box} body{margin:0}
header{background:#172033;color:#fff;padding:14px 24px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
header h1{margin:0;margin-right:auto;font-size:22px}
.header-user{background:#2b3850;padding:8px 11px;border-radius:8px}
.cart-button,.orders-button,.logout-button{padding:9px 13px;border-radius:8px;text-decoration:none;cursor:pointer}
.cart-button{background:#2457d6;color:#fff;border:1px solid #2457d6}
.orders-button{background:#fff;color:#172033;border:1px solid #fff}
.logout-form{margin:0}.logout-button{background:transparent;color:#fff;border:1px solid #fff}
main{width:min(1100px,calc(100% - 32px));margin:28px auto 80px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px}
.product{background:#fff;border:1px solid #dce2ec;border-radius:14px;padding:18px}
.product-image{height:130px;display:grid;place-items:center;background:#eef3f8;border-radius:10px;font-size:54px}
.category{color:#667085;font-size:13px;margin-bottom:4px}.product h2{margin:4px 0 8px;font-size:19px}.price{font-size:21px;font-weight:800}
.product button{width:100%;padding:10px 14px;border-radius:8px;border:1px solid #2457d6;background:#2457d6;color:#fff;cursor:pointer}
</style>
</head>
<body>
<header>
  <h1>QA Test Store</h1>
  <span class="header-user" data-testid="logged-in-user">User: {{ username }}</span>
  <a href="/orders" class="orders-button" data-testid="orders-link">Orders</a>
  <a href="/cart" class="cart-button" data-testid="cart-link">Cart ({{ cart_count }})</a>
  <form class="logout-form" method="post" action="/logout">
    <button type="submit" class="logout-button" data-testid="logout-button"
      onclick="localStorage.removeItem('authToken');localStorage.removeItem('username');">Logout</button>
  </form>
</header>

<main>
  <h1>Products</h1>
  <div class="grid">
    {% for product in products %}
    <div class="product" data-testid="product-{{ product.id }}">
      <div class="product-image">📦</div>
      <p class="category">{{ product.category }}</p>
      <h2 data-testid="product-name-{{ product.id }}">{{ product.name }}</h2>
      <p class="price" data-testid="price-{{ product.id }}">€{{ "%.2f"|format(product.price) }}</p>
      <form method="post" action="/add-to-cart/{{ product.id }}">
        <button type="submit" data-testid="add-product-{{ product.id }}">Add to Cart</button>
      </form>
    </div>
    {% endfor %}
  </div>
</main>
</body>
</html>
"""

# ============================================================
# HTML TEMPLATE: SHOPPING CART PAGE
# ============================================================
CART_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shopping Cart</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#172033;background:#f5f7fb}
*{box-sizing:border-box}body{margin:0}header{background:#172033;color:white;padding:14px 24px;display:flex;align-items:center;gap:14px}header h1{margin:0;margin-right:auto;font-size:22px}header a{color:white}
main{width:min(900px,calc(100% - 32px));margin:28px auto}.cart-item{background:white;border:1px solid #dce2ec;border-radius:12px;padding:16px;margin-bottom:12px;display:grid;grid-template-columns:1fr auto auto;gap:14px;align-items:center}.cart-item h3{margin:0 0 5px}.cart-item p{margin:0;color:#667085}
input{width:90px;padding:8px;border:1px solid #b8c1cf;border-radius:7px}button,.button{padding:9px 13px;border-radius:8px;border:1px solid #2457d6;background:#2457d6;color:white;cursor:pointer;text-decoration:none;display:inline-block}.remove{background:#c93636;border-color:#c93636}.total{margin-top:18px;padding:16px;background:white;border:1px solid #dce2ec;border-radius:12px;font-size:22px;font-weight:800}.actions{margin-top:16px;display:flex;gap:10px;flex-wrap:wrap}.checkout{background:#16803c;border-color:#16803c}.empty{background:white;border:1px solid #dce2ec;border-radius:12px;padding:20px}
</style>
</head>
<body>
<header><h1>Shopping Cart</h1><span data-testid="logged-in-user">User: {{ username }}</span><a href="/store">Back to Store</a></header>
<main>
{% if items %}
  {% for item in items %}
  <div class="cart-item" data-testid="cart-item-{{ item.id }}">
    <div class="info"><h3>{{ item.name }}</h3><p>€{{ "%.2f"|format(item.price) }} each</p></div>
    <form method="post" action="/update-cart/{{ item.id }}">
      <label>Quantity
        <input type="number" name="quantity" min="1" max="10" value="{{ item.quantity }}" data-testid="quantity-{{ item.id }}">
      </label>
      <button type="submit" data-testid="update-product-{{ item.id }}">Update</button>
    </form>
    <form method="post" action="/remove-from-cart/{{ item.id }}">
      <button type="submit" class="remove" data-testid="remove-product-{{ item.id }}">Remove</button>
    </form>
  </div>
  {% endfor %}

  <div class="total" data-testid="cart-total">Total: €{{ "%.2f"|format(total) }}</div>
  <div class="actions">
    <a href="/store" class="button">Continue Shopping</a>
    <a href="/checkout" class="button checkout" data-testid="checkout-button">Checkout</a>
  </div>
{% else %}
  <div class="empty">
    <h2>Your cart is empty</h2>
    <a href="/store" class="button" data-testid="back-to-store">Back to Store</a>
  </div>
{% endif %}
</main>
</body>
</html>
"""

# ============================================================
# HTML TEMPLATE: CHECKOUT PAGE
# ============================================================
CHECKOUT_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Checkout</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#172033;background:#f5f7fb}
*{box-sizing:border-box}body{margin:0}main{width:min(760px,calc(100% - 32px));margin:28px auto}.card{background:white;border:1px solid #dce2ec;border-radius:14px;padding:22px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}label{display:block;font-weight:650;margin-top:12px}input,select{width:100%;padding:10px;margin-top:5px;border:1px solid #b8c1cf;border-radius:8px}button,.button{margin-top:18px;padding:11px 15px;border-radius:8px;border:1px solid #16803c;background:#16803c;color:white;cursor:pointer;text-decoration:none;display:inline-block}.warning{background:#fff6dd;padding:10px;border-radius:8px;margin-bottom:14px}.total{font-size:22px;font-weight:800;margin-top:16px}.inline{display:flex;align-items:center;gap:8px;font-weight:500}.inline input{width:auto;margin:0}
</style>
</head>
<body>
<main><div class="card">
<h1>Checkout</h1>
<p class="warning">QA training only. Do not enter real payment information.</p>
<form method="post" action="/checkout">
  <h2>Customer details</h2>
  <div class="grid">
    <div><label for="firstName">First name</label><input id="firstName" name="first_name" required data-testid="checkout-first-name"></div>
    <div><label for="lastName">Last name</label><input id="lastName" name="last_name" required data-testid="checkout-last-name"></div>
  </div>
  <label for="email">Email</label><input id="email" name="email" type="email" required data-testid="checkout-email">
  <label for="address">Address</label><input id="address" name="address" required data-testid="checkout-address">
  <label for="country">Country</label>
  <select id="country" name="country" required data-testid="checkout-country">
    <option value="">Choose a country</option><option value="AT">Austria</option><option value="GR">Greece</option><option value="DE">Germany</option><option value="BG">Bulgaria</option>
  </select>

  <h2>Fake payment details</h2>
  <label for="cardName">Name on card</label><input id="cardName" name="card_name" required data-testid="card-name">
  <label for="cardNumber">Card number</label><input id="cardNumber" name="card_number" placeholder="4111 1111 1111 1111" required data-testid="card-number">
  <div class="grid">
    <div><label for="cardExpiry">Expiry</label><input id="cardExpiry" name="card_expiry" placeholder="12/30" required data-testid="card-expiry"></div>
    <div><label for="cardCvv">CVV</label><input id="cardCvv" name="card_cvv" placeholder="123" required data-testid="card-cvv"></div>
  </div>

  <label class="inline" style="margin-top:18px">
    <input type="checkbox" name="confirm_order" required data-testid="confirm-order-checkbox">
    I confirm this is a fake QA test order.
  </label>

  <div class="total" data-testid="checkout-total">Total: €{{ "%.2f"|format(total) }}</div>
  <button type="submit" data-testid="place-order-button">Place Order</button>
  <a href="/cart" class="button" style="background:#fff;color:#172033;border-color:#aeb9c8">Back to Cart</a>
</form>
</div></main>
</body>
</html>
"""


# ============================================================
# HTML TEMPLATE: ORDER HISTORY PAGE
# IMPORTANT:
# - View Order and Delete Order buttons are rendered here.
# - Search for "ORDER HISTORY ACTION BUTTONS" to edit them.
# ============================================================
ORDERS_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Order History</title>

<style>
:root{
    font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
    color:#172033;
    background:#f5f7fb
}
*{box-sizing:border-box}
body{margin:0}

header{
    background:#172033;
    color:white;
    padding:14px 24px;
    display:flex;
    align-items:center;
    gap:14px
}
header h1{
    margin:0;
    margin-right:auto;
    font-size:22px
}
header a{
    color:white;
    text-decoration:none
}

header a[data-testid="orders-back-to-store"]{
    padding:8px 12px;
    border:1px solid white;
    border-radius:8px;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    min-height:36px
}

header button{
    padding:8px 12px;
    border-radius:8px;
    border:1px solid white;
    background:transparent;
    color:white;
    cursor:pointer
}

main{
    width:min(1000px,calc(100% - 32px));
    margin:28px auto 80px
}

.loading,
.error-box,
.empty{
    background:white;
    border:1px solid #dce2ec;
    border-radius:14px;
    padding:22px
}

.error-box{
    color:#9b1c1c;
    background:#fff0f0
}

.order{
    background:white;
    border:1px solid #dce2ec;
    border-radius:14px;
    padding:18px;
    margin-bottom:16px
}

.order-header{
    display:flex;
    justify-content:space-between;
    gap:16px;
    flex-wrap:wrap;
    align-items:flex-start
}

.order-number{
    font-weight:800;
    font-size:18px
}
.order-actions{
    display:flex;
    gap:10px;
    margin-top:12px;
    align-items:center;
    flex-wrap:wrap
}

.order-actions .button,
.order-actions .delete-button{
    min-width:110px;
    height:40px;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    margin:0;
    padding:0 14px;
    border-radius:8px;
    font-weight:600;
    line-height:1;
    box-sizing:border-box
}

.delete-button{
    border:0;
    background:#c62828;
    color:white;
    cursor:pointer
}

.meta{
    color:#667085;
    margin-top:4px
}

.total{
    font-weight:800;
    font-size:20px
}

table{
    width:100%;
    border-collapse:collapse;
    margin-top:16px
}

th,td{
    text-align:left;
    padding:9px;
    border-bottom:1px solid #e1e6ee
}

.button{
    display:inline-block;
    margin-top:14px;
    padding:9px 13px;
    border-radius:8px;
    background:#2457d6;
    color:white;
    text-decoration:none
}
</style>
</head>

<body>

<header>
    <h1>Order History</h1>

    <span data-testid="logged-in-user">
        User: {{ username }}
    </span>

    <span data-testid="logged-in-role">
        Role: {{ role }}
    </span>

    {% if role == "admin" %}
    <a
        href="/store"
        data-testid="orders-back-to-store">
        Back to Store
    </a>
    {% endif %}

    <form method="post" action="/logout" style="margin:0">
        <button
            type="submit"
            data-testid="orders-logout-button"
            onclick="
                localStorage.removeItem('authToken');
                localStorage.removeItem('username');
                localStorage.removeItem('role');
            ">
            Logout
        </button>
    </form>
</header>

<main id="ordersContainer" data-testid="orders-container">

    <div
        class="loading"
        data-testid="orders-loading">
        Loading orders...
    </div>

</main>


<script>
function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
}


function renderNoOrders(message) {
    const container = document.getElementById("ordersContainer");

    container.innerHTML = `
        <div
            class="empty"
            data-testid="no-orders">

            <h2 data-testid="no-orders-heading">
                ${escapeHtml(message || "No orders yet")}
            </h2>

            <p>
                Complete a checkout and the order will appear here.
            </p>

            <a
                href="/store"
                class="button">
                Go to Store
            </a>

        </div>
    `;
}


function renderOrders(orders) {
    const container = document.getElementById("ordersContainer");

    const ordersHtml = orders.map((order, orderIndex) => {

        const items = order.items || [];

        // ============================================================
        // ORDER HISTORY ACTION BUTTONS
        // Add/change View Order or Delete Order buttons in this block.
        // Delete is intentionally available only to admin users.
        // ============================================================
        const deleteButton = "{{ role }}" === "admin"
            ? `
                <form
                    method="post"
                    action="/orders/${encodeURIComponent(order.order_number)}/delete"
                    style="display:inline"
                    onsubmit="return confirm('Are you sure you want to delete this order?');">

                    <button
                        type="submit"
                        class="delete-button"
                        data-testid="delete-order-${escapeHtml(order.order_number)}">
                        Delete Order
                    </button>
                </form>
            `
            : "";

        const itemRows = items.map((item, itemIndex) => `
            <tr data-testid="order-item-${itemIndex + 1}">
                <td>${escapeHtml(item.name)}</td>
                <td>${escapeHtml(item.quantity)}</td>
                <td>€${Number(item.price).toFixed(2)}</td>
                <td>
                    €${(
                        Number(item.price) *
                        Number(item.quantity)
                    ).toFixed(2)}
                </td>
            </tr>
        `).join("");

        return `
            <section
                class="order"
                data-testid="order-${escapeHtml(order.order_number)}">

                <div class="order-header">

                    <div>
                        <div
                            class="order-number"
                            data-testid="order-number-${orderIndex + 1}">
                            ${escapeHtml(order.order_number)}
                        </div>

                        <div class="meta">
                            ${escapeHtml(order.created_at)}
                        </div>

                        <div class="meta">
                            Customer:
                            ${escapeHtml(order.customer_name)}
                        </div>

                        <div class="meta">
                            Email:
                            ${escapeHtml(order.email)}
                        </div>
                    </div>

                    <div
                        class="total"
                        data-testid="order-total-${orderIndex + 1}">
                        €${Number(order.total).toFixed(2)}
                    </div>

                </div>

                <table>
                    <thead>
                        <tr>
                            <th>Product</th>
                            <th>Quantity</th>
                            <th>Price</th>
                            <th>Line total</th>
                        </tr>
                    </thead>

                    <tbody>
                        ${itemRows}
                    </tbody>
                </table>

                <div class="order-actions">

                    <a
                        href="/orders/${encodeURIComponent(order.order_number)}"
                        class="button"
                        data-testid="view-order-${escapeHtml(order.order_number)}">
                        View Order
                    </a>

                    ${deleteButton}

                </div>

            </section>
        `;
    }).join("");

    container.innerHTML = `
        <h2 data-testid="orders-count">
            ${orders.length} order(s)
        </h2>

        ${ordersHtml}
    `;
}


// ============================================================
// ORDER HISTORY API LOADER
// Fetches GET /api/orders and then calls renderOrders().
// ============================================================
async function loadOrders() {
    const container = document.getElementById("ordersContainer");
    const token = localStorage.getItem("authToken");

    const headers = {};

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    try {
        const response = await fetch("/api/orders", {
            method: "GET",
            headers: headers
        });

        const payload = await response.json();

        if (!response.ok) {
            container.innerHTML = `
                <div
                    class="error-box"
                    data-testid="orders-error">
                    ${escapeHtml(
                        payload.error ||
                        "Unable to load orders"
                    )}
                </div>
            `;

            return;
        }

        /*
           Real API:
           {
               "orders": [...],
               "data": [...],
               "message": "..."
           }

           Your Playwright mocked response can be:
           {
               "data": [],
               "message": "No orders yet"
           }
        */
        const orders = payload.data ?? payload.orders ?? [];

        if (orders.length === 0) {
            renderNoOrders(
                payload.message || "No orders yet"
            );

            return;
        }

        renderOrders(orders);

    } catch (error) {
        container.innerHTML = `
            <div
                class="error-box"
                data-testid="orders-error">
                Failed to load orders
            </div>
        `;
    }
}


loadOrders();
</script>

</body>
</html>
"""
# ============================================================
# HTML TEMPLATE: SINGLE ORDER DETAILS PAGE
# IMPORTANT:
# - Back to Orders and Delete Order buttons are near the bottom.
# ============================================================
ORDER_DETAILS_HTML = """
<!doctype html>
<html lang="en">

<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>Order Details</title>

<style>

:root{
    font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
    color:#172033;
    background:#f5f7fb
}

*{
    box-sizing:border-box
}

body{
    margin:0
}

header{
    background:#172033;
    color:white;
    padding:14px 24px;
    display:flex;
    align-items:center;
    gap:14px
}

header h1{
    margin:0;
    margin-right:auto
}

header a{
    color:white;
    text-decoration:none;
    padding:8px 12px;
    border:1px solid white;
    border-radius:8px;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    min-height:36px
}

main{
    width:min(900px,calc(100% - 32px));
    margin:30px auto
}

.card{
    background:white;
    border:1px solid #dce2ec;
    border-radius:14px;
    padding:24px
}

.meta{
    color:#667085;
    margin:7px 0
}

.total{
    font-size:22px;
    font-weight:800;
    margin-top:20px
}

table{
    width:100%;
    border-collapse:collapse;
    margin-top:24px
}

th,
td{
    text-align:left;
    padding:10px;
    border-bottom:1px solid #e1e6ee
}

.actions{
    display:flex;
    gap:10px;
    margin-top:20px;
    align-items:center
}

.button{
    display:inline-block;
    padding:10px 14px;
    border-radius:8px;
    background:#2457d6;
    color:white;
    text-decoration:none;
    border:0;
    cursor:pointer
}

.delete-button{
    background:#c62828;
    min-width:120px;
    height:40px;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    margin:0;
    font-weight:600
}

</style>
</head>

<body>

<header>

    <h1>Order Details</h1>

    <span>
        User: {{ username }}
    </span>

    <a href="/orders">
        Back to Orders
    </a>

</header>

<main>

<div class="card">

    <h2 data-testid="order-details-number">
        {{ order.order_number }}
    </h2>

    <div class="meta">
        Date: {{ order.created_at }}
    </div>

    <div class="meta">
        Customer: {{ order.customer_name }}
    </div>

    <div class="meta">
        Email: {{ order.email }}
    </div>

    <div class="meta">
        Address: {{ order.address }}
    </div>

    <div class="meta">
        Country: {{ order.country }}
    </div>

    <table data-testid="order-details-table">

        <thead>
        <tr>
            <th>Product</th>
            <th>Quantity</th>
            <th>Price</th>
            <th>Line total</th>
        </tr>
        </thead>

        <tbody>

        {% for item in order["items"] %}

        <tr>
            <td>{{ item.name }}</td>

            <td>
                {{ item.quantity }}
            </td>

            <td>
                €{{ "%.2f"|format(item.price) }}
            </td>

            <td>
                €{{ "%.2f"|format(
                    item.price * item.quantity
                ) }}
            </td>
        </tr>

        {% endfor %}

        </tbody>

    </table>

    <div
        class="total"
        data-testid="order-details-total">

        Total:
        €{{ "%.2f"|format(order.total) }}

    </div>

    <!-- ======================================================
         ORDER DETAILS ACTION BUTTONS
         Admin-only Delete Order lives here.
         Back to Orders is in the header above.
         ====================================================== -->
    <div class="actions">

        {% if role == "admin" %}

        <form
            method="post"
            action="{{ url_for(
                'delete_order_route',
                order_number=order.order_number
            ) }}"
            onsubmit="return confirm(
                'Are you sure you want to delete this order?'
            );">

            <button
                type="submit"
                class="button delete-button"
                data-testid="delete-order">

                Delete Order

            </button>

        </form>

        {% endif %}

    </div>

</div>

</main>

</body>
</html>
"""

# ============================================================
# HTML TEMPLATE: ORDER SUCCESS PAGE
# ============================================================
SUCCESS_HTML = """
<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Order Successful</title>
<style>body{font-family:system-ui;background:#f5f7fb;padding:40px;color:#172033}.card{max-width:600px;margin:auto;background:white;border:1px solid #dce2ec;border-radius:14px;padding:28px}a{display:inline-block;margin-top:18px;padding:10px 14px;border-radius:8px;background:#2457d6;color:white;text-decoration:none}</style>
</head><body><main class="card">
<h1 data-testid="order-success">Order Successful</h1>
<p data-testid="order-number">Order number: {{ order_number }}</p>
<p>Thanks, {{ username }}. This was a fake QA test order.</p>
<a href="/store" data-testid="back-to-store">Back to Store</a>
<a href="/orders" data-testid="view-orders">View Order History</a>
</main></body></html>
"""
# ============================================================
# HELPER FUNCTIONS
# General authentication/cart helpers live in this section.
# ============================================================

def require_login():
    return bool(session.get("user"))


def current_role():
    return session.get("role")


def is_admin():
    return current_role() == "admin"


def protect_admin_page():
    if not require_login():
        return redirect(url_for("index"))

    if not is_admin():
        return redirect(url_for("orders"))

    return None


def get_bearer_identity():
    authorization = request.headers.get("Authorization", "")

    if not authorization.startswith("Bearer "):
        return None, "Invalid or missing bearer token"

    token = authorization.removeprefix("Bearer ").strip()

    if not token:
        return None, "Invalid or missing bearer token"

    token_data = TOKENS.get(token)

    if not token_data:
        return None, "Invalid or missing bearer token"

    if time.time() >= token_data["expires_at"]:
        TOKENS.pop(token, None)
        return None, "Token expired"

    return {
        "username": token_data["username"],
        "role": token_data["role"]
    }, None



# ============================================================
# ORDER HELPER FUNCTIONS
# Add future order lookup/filter/delete helper functions here.
# ============================================================
def get_orders_for_user(username):
    return ORDER_HISTORY.setdefault(username, [])


def get_orders():
    username = session.get("user")

    if not username:
        return []

    return get_orders_for_user(username)

def get_all_orders():
    all_orders = []

    for orders in ORDER_HISTORY.values():
        all_orders.extend(orders)

    all_orders.sort(
        key=lambda order: order["order_number"],
        reverse=True
    )

    return all_orders

def find_order_by_number(order_number):
    for username, orders in ORDER_HISTORY.items():
        for order in orders:
            if order["order_number"] == order_number:
                return order

    return None


def delete_order_by_number(order_number):
    for username, orders in ORDER_HISTORY.items():
        for index, order in enumerate(orders):
            if order["order_number"] == order_number:
                del orders[index]
                return True

    return False

def get_cart():
    return session.get("cart", {})


def get_cart_count():
    return sum(get_cart().values())


def get_product(product_id):
    return next((product for product in PRODUCTS if product["id"] == product_id), None)


def build_cart_items():
    cart = get_cart()
    items = []
    total = 0.0

    for product_id_string, quantity in cart.items():
        product = get_product(int(product_id_string))
        if not product:
            continue

        items.append({**product, "quantity": quantity})
        total += product["price"] * quantity

    return items, total

# ============================================================
# FLASK ROUTES START HERE
# Page URLs and form actions are defined below.
# ============================================================
@app.get("/")
def index():
    if require_login():
        if is_admin():
            return redirect(url_for("store"))

        return redirect(url_for("orders"))

    return render_template_string(LOGIN_HTML)


@app.get("/terms")
def terms():
    return TERMS_HTML


@app.post("/login")
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    remember = request.form.get("remember") == "on"

    user = USERS.get(username)

    if user and password == user["password"]:
        token = secrets.token_urlsafe(32)

        session.permanent = remember
        session["user"] = username
        session["role"] = user["role"]
        session["auth_token"] = token

        TOKENS[token] = {
            "username": username,
            "role": user["role"],
            "expires_at": time.time() + TOKEN_EXPIRY_SECONDS
        }

        return jsonify({
            "message": "Login successful",
            "username": username,
            "role": user["role"],
            "token": token,
            "token_type": "Bearer"
        }), 200

    return jsonify({
        "error": "Invalid username or password"
    }), 401


@app.post("/logout")
def logout():
    token = session.get("auth_token")

    if token:
        TOKENS.pop(token, None)

    session.clear()
    return redirect(url_for("index"))


@app.get("/store")
def store():
    restriction = protect_admin_page()

    if restriction:
        return restriction

    return render_template_string(
        STORE_HTML,
        products=PRODUCTS,
        cart_count=get_cart_count(),
        username=session["user"]
    )


@app.post("/add-to-cart/<int:product_id>")
def add_to_cart(product_id):
    restriction = protect_admin_page()

    if restriction:
        return restriction

    if not get_product(product_id):
        return "Product not found", 404

    cart = get_cart()
    key = str(product_id)
    cart[key] = cart.get(key, 0) + 1
    session["cart"] = cart

    return redirect(url_for("store"))


# ============================================================
# ORDER PAGE ROUTES
# /orders                         -> order history
# /orders/<order_number>          -> single order details
# /orders/<order_number>/delete   -> delete order (admin only)
# Add future order-page routes in this area.
# ============================================================
@app.get("/orders")
def orders():
    if not require_login():
        return redirect(url_for("index"))

    return render_template_string(
        ORDERS_HTML,
        username=session["user"],
        role=session["role"]
    )

@app.get("/orders/<order_number>")
def order_details(order_number):

    if not require_login():
        return redirect(url_for("index"))

    order = find_order_by_number(order_number)

    if not order:
        return "Order not found", 404

    return render_template_string(
        ORDER_DETAILS_HTML,
        order=order,
        username=session["user"],
        role=session["role"]
    )


@app.post("/orders/<order_number>/delete")
def delete_order_route(order_number):

    restriction = protect_admin_page()

    if restriction:
        return restriction

    deleted = delete_order_by_number(order_number)

    if not deleted:
        return "Order not found", 404

    return redirect(url_for("orders"))


@app.get("/cart")
def cart():
    restriction = protect_admin_page()

    if restriction:
        return restriction

    items, total = build_cart_items()

    return render_template_string(
        CART_HTML,
        items=items,
        total=total,
        username=session["user"]
    )


@app.post("/update-cart/<int:product_id>")
def update_cart(product_id):
    restriction = protect_admin_page()

    if restriction:
        return restriction

    cart = get_cart()
    key = str(product_id)

    if key not in cart:
        return redirect(url_for("cart"))

    try:
        quantity = int(request.form.get("quantity", "1"))
    except ValueError:
        quantity = 1

    cart[key] = max(1, min(quantity, 10))
    session["cart"] = cart

    return redirect(url_for("cart"))


@app.post("/remove-from-cart/<int:product_id>")
def remove_from_cart(product_id):
    restriction = protect_admin_page()

    if restriction:
        return restriction

    cart = get_cart()
    cart.pop(str(product_id), None)
    session["cart"] = cart

    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    restriction = protect_admin_page()

    if restriction:
        return restriction

    items, total = build_cart_items()

    if not items:
        return redirect(url_for("cart"))

    if request.method == "POST":
        order_number = "TEST-" + str(int(time.time()))

        order = {
            "order_number": order_number,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": (
                request.form.get("first_name", "") + " " +
                request.form.get("last_name", "")
            ).strip(),
            "email": request.form.get("email", ""),
            "address": request.form.get("address", ""),
            "country": request.form.get("country", ""),
            "items": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "price": item["price"],
                    "quantity": item["quantity"]
                }
                for item in items
            ],
            "total": round(total, 2)
        }

        get_orders().insert(0, order)

        session["cart"] = {}

        return render_template_string(
            SUCCESS_HTML,
            order_number=order_number,
            username=session["user"]
        )

    return render_template_string(CHECKOUT_HTML, total=total)


# ============================================================
# API ROUTES
# Bearer-token endpoints used by Playwright/API tests.
# ============================================================
@app.get("/api/user")
def api_user():
    identity, auth_error = get_bearer_identity()

    if not identity:
        return jsonify({
            "error": auth_error
        }), 401

    return jsonify({
        "username": identity["username"],
        "role": identity["role"],
        "authenticated": True
    }), 200


# ============================================================
# ORDER API: GET ALL ORDERS
# Used by the Order History page and Playwright network tests.
# ============================================================
@app.get("/api/orders")
def api_orders():
    identity, auth_error = get_bearer_identity()

    if not identity:
        return jsonify({
            "error": auth_error
        }), 401

    orders = get_all_orders()

    return jsonify({
        "username": identity["username"],
        "role": identity["role"],
        "orders": orders,
        "data": orders,
        "message": (
            "No orders yet"
            if not orders
            else "Orders loaded successfully"
        )
    }), 200


@app.post("/api/test/expire-token")
def expire_token_for_test():
    authorization = request.headers.get("Authorization", "")

    if not authorization.startswith("Bearer "):
        return jsonify({
            "error": "Invalid or missing bearer token"
        }), 401

    token = authorization.removeprefix("Bearer ").strip()
    token_data = TOKENS.get(token)

    if not token_data:
        return jsonify({
            "error": "Invalid or missing bearer token"
        }), 401

    token_data["expires_at"] = time.time() - 1

    return jsonify({
        "message": "Token forced to expire for test purposes"
    }), 200


# ============================================================
# ORDER API: CREATE ORDER
# Used by APIUtils.createOrder() in the Playwright tests.
# ============================================================
@app.post("/api/orders")
def create_api_order():
    identity, auth_error = get_bearer_identity()

    if not identity:
        return jsonify({
            "error": auth_error
        }), 401

    if identity["role"] != "admin":
        return jsonify({
            "error": "Admin access required"
        }), 403

    username = identity["username"]

    payload = request.get_json(silent=True) or {}
    requested_items = payload.get("items", [])

    if not requested_items:
        return jsonify({
            "error": "No items supplied"
        }), 400

    order_items = []
    total = 0.0

    for requested_item in requested_items:
        product_id = requested_item.get("productId")
        quantity = requested_item.get("quantity", 1)

        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            return jsonify({
                "error": "productId and quantity must be numbers"
            }), 400

        product = get_product(product_id)

        if not product:
            return jsonify({
                "error": f"Product {product_id} not found"
            }), 404

        quantity = max(1, min(quantity, 10))

        order_items.append({
            "id": product["id"],
            "name": product["name"],
            "price": product["price"],
            "quantity": quantity
        })

        total += product["price"] * quantity

    order_number = "TEST-" + str(int(time.time() * 1000))

    customer_name = (
        str(payload.get("firstName", "")).strip() + " " +
        str(payload.get("lastName", "")).strip()
    ).strip()

    order = {
        "order_number": order_number,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "customer_name": customer_name,
        "email": str(payload.get("email", "")),
        "address": str(payload.get("address", "")),
        "country": str(payload.get("country", "")),
        "items": order_items,
        "total": round(total, 2)
    }

    get_orders_for_user(username).insert(0, order)

    return jsonify({
        "message": "Order created successfully",
        "orderId": order_number,
        "username": username,
        "total": round(total, 2)
    }), 201

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3002))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
