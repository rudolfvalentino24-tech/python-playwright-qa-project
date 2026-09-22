# Store strategy coverage

Mapping for *Store Application – E2E, Smoke & Release Test Strategy*, version 1.1.
This is a mapping of implemented assertions, not a statement that every test passes.
The same test can satisfy several plan IDs; smoke and release select existing tests with markers.
Each BDD example produces a separate pytest result. Steps within E2E-001 share one result.

## E2E plan

| Plan IDs | Implementation |
| --- | --- |
| AUTH-01–05 | `features/authentication.feature`: valid/invalid login, terms, logout |
| AUTH-06 | `features/authorization.feature`: logged-out Store access |
| STORE-01–03 | `features/store.feature`: Store and catalog; names/prices checked against `data/products.json` |
| CART-01–06 | `features/cart.feature`: selection, exact information, totals, removal, empty state |
| CHECK-01 | E2E-001: navigate from cart and assert Checkout page |
| CHECK-02 | E2E-001: submit valid customer/payment information and assert success |
| CHECK-03 | `features/checkout.feature`: nine required fields and confirmation checkbox |
| CHECK-04 | Checkout scenario checks multi-product subtotal against cart and checkout; E2E-001 checks order total |
| CHECK-05 | E2E-001: capture the nonempty generated order number and open that order |
| CHECK-06 (additional) | Checkout rejects a malformed email |
| ORDER-01 | E2E-001: created order appears in history |
| ORDER-02 | E2E-001: select the exact created order ID |
| ORDER-03 | E2E-001: exact detail URL and displayed order number |
| ORDER-04 | E2E-001: customer name, email, address, country |
| ORDER-05 | E2E-001: product name, quantity, unit price, line total; ROLE-02 also checks multiple products |
| ORDER-06 | E2E-001: exact order total compared with captured cart total |
| ORDER-07–08 | `features/order_management.feature`: deletion from details/history, absence after reload |
| ROLE-01–05 | `features/authorization.feature`: viewer history/details and Store/Cart/Checkout restrictions |
| ROLE-06 | API `test_viewer_cannot_create_order` and `test_viewer_cannot_submit_checkout_directly` |
| ROLE-07 | Authorization feature checks hidden controls; API `test_viewer_cannot_delete_order_by_direct_request` checks server enforcement |
| ROLE-08 | E2E-001: admin Store, Cart, Checkout, creation and deletion |
| SESSION-01 | `features/session.feature`: cart and authenticated navigation persist |
| SESSION-02 | Session outline: Store, Cart, Checkout, History and real order details inaccessible after logout; API token revocation also tested |
| SESSION-03 | API `test_expired_token_is_rejected`, both protected GET endpoints |
| SESSION-04 | API `test_api_rejects_missing_or_invalid_token` and protected order creation |

## Smoke plan

| Plan IDs | Smoke-marked implementation |
| --- | --- |
| SMK-UI-01–03 | E2E-001: login page, login, Store navigation |
| SMK-UI-04 | STORE-02: products displayed |
| SMK-UI-05–11 | E2E-001: cart, checkout, order creation/history/details, deletion and logout |
| SMK-UI-12 | ROLE-01: viewer history |
| SMK-UI-13 | ROLE-03: viewer denied Store; the same outline also checks Cart/Checkout |
| SMK-API-01, 03 | `test_login_token_and_identity[admin]` |
| SMK-API-02 | Invalid username/password examples of `test_login_rejects_invalid_or_missing_credentials` |
| SMK-API-04–06 | `test_created_order_is_listed_with_correct_details[admin]` |
| SMK-API-07 | `test_created_order_is_listed_with_correct_details[viewer]` |
| SMK-API-08 | `test_viewer_cannot_create_order` |
| SMK-API-09–10 | `test_api_rejects_missing_or_invalid_token` |

## Release UI plan

| Plan IDs | Implementation |
| --- | --- |
| REL-UI-AUTH-01, 04, 05, 08, 09 | AUTH-01, 02, 03, 04, 05 respectively |
| REL-UI-AUTH-02 | Named second-admin login scenario in authentication feature |
| REL-UI-AUTH-03 | ROLE-01 viewer UI login |
| REL-UI-AUTH-06–07 | Missing Username/Password outline |
| REL-UI-AUTH-10 | SESSION-02 protected pages after logout |
| REL-UI-STORE-01–02 | STORE-01–02 |
| REL-UI-STORE-03–05 | STORE-03: exact six-product catalog, names, prices and buttons |
| REL-UI-STORE-06 | CART-01 and E2E-001 |
| REL-UI-CART-01–07 | CART-01–06; CART-03 checks name and price separately |
| REL-UI-CHK-01–02, 08–09 | E2E-001 |
| REL-UI-CHK-03–06 | Required-field examples of CHECK-03 |
| REL-UI-CHK-07 | CHECK-04 |
| REL-UI-ORD-01–06 | E2E-001 (ORDER-01–06 mapping above) |
| REL-UI-ORD-07–08 | ORDER-07–08 |
| REL-UI-ORD-09 | Named authorization scenario: second admin sees the first admin's seeded order |
| REL-UI-ROLE-01–04 | E2E-001 admin Store/Cart/Checkout/deletion |
| REL-UI-ROLE-05–10 | ROLE-01–05, ROLE-07 plus direct deletion request rejection |

## Release API plan

All API tests are in `../api/test_store_api.py` and have the `release` marker.

| Plan IDs | Implementation |
| --- | --- |
| REL-API-AUTH-01–02, 07–08 | `test_login_token_and_identity`: both roles, token and identity |
| REL-API-AUTH-03–06 | `test_login_rejects_invalid_or_missing_credentials` |
| REL-API-ORD-01–07 | `test_created_order_is_listed_with_correct_details`: created ID, admin/viewer GET, full items/customer/total |
| REL-API-ORD-08 | `test_invalid_order_items_are_rejected`: invalid IDs/quantities and nonexistent product |
| REL-API-ORD-09 | `test_required_order_data_is_rejected_when_missing`: each customer field and items; empty-items case also tested |
| REL-API-ORD-10 | `test_viewer_cannot_create_order` |
| REL-API-SEC-01–02 | Missing/invalid token GET and POST cases |
| REL-API-SEC-03 | Expired token cases |
| REL-API-SEC-04 | Admin creates/retrieves orders with its token |
| REL-API-SEC-05–06 | Viewer reads orders but cannot create; direct checkout/deletion also denied |
| REL-API-SEC-07 | `test_login_token_and_identity` |

## Execution

From the project root, using the configured project interpreter:

```powershell
# Optional: point at a running local Store; otherwise config.py uses Render.
$env:STORE_URL = "http://127.0.0.1:3002"
$env:HEADLESS = "1"

python -m pytest playwright/e2e_bdd playwright/api -m smoke --browser_name chrome --html=smoke-report.html --self-contained-html
python -m pytest playwright/e2e_bdd --browser_name chrome --html=e2e-report.html --self-contained-html
python -m pytest playwright/e2e_bdd playwright/api -m release --browser_name chrome --html=release-report.html --self-contained-html
python -m pytest playwright/e2e_bdd -m release --browser_name firefox --html=release-firefox-report.html --self-contained-html
```

Jenkins sets headless mode automatically. Smoke failures and release failures keep pytest's nonzero exit code.
API tests do not require a browser and need only one release run. UI validation uses browser validity state rather
than English validation messages, so Chromium and Firefox can share the scenarios.

Orders for the purchase/deletion journeys are created through the UI. Permission/session setup uses API fixtures
and fresh orders rather than data from previous runs. Cleanup uses a separate admin session and removes only
captured test order IDs. API clients use isolated request contexts, revoke their tokens and close after each test.
The viewer's training credentials and expected catalog are stored in JSON beside the existing admin credentials.

These are functional UI/API checks. Native form validation coverage does not prove server-side validation;
the missing-data API tests deliberately check that separately. No tests are skipped or marked expected-failure
to hide application defects. The legacy standalone viewer/token tests remain available outside these suite commands.

## Local verification — 2026-09-22

All runs used an isolated local instance of `qa_testing_playground/store.py`, with headless browsers.
The suite now contains 46 BDD UI cases and 30 API cases (76 total).

| Run | Result | Report |
| --- | --- | --- |
| Chromium UI + API release coverage | 71 passed, 5 failed | [Release report](../../artifacts/local-review/store-release-chromium.html) |
| Chromium UI + API smoke selection | 17 passed, 59 deselected | [Smoke report](../../artifacts/local-review/store-smoke.html) |
| Firefox UI coverage | 46 passed | [Firefox report](../../artifacts/local-review/store-firefox.html) |

The five failures are the missing-customer-field API cases documented in [KNOWN_ISSUES.md](KNOWN_ISSUES.md).
They block a fully passing release run. Generated HTML reports are local artifacts and are ignored by Git.
Pytest also reports upstream Gherkin deprecation warnings under Python 3.14. The optional IDE inspection
could not complete because PyCharm reported a PSI/index mismatch; the executed tests imported the changed modules.
