# Findings from the remaining Store strategy tests

## Resolved locally: API accepts orders without required customer data

Plan reference: REL-API-ORD-09 (missing required order data).
Test: `playwright/api/test_store_api.py::test_required_order_data_is_rejected_when_missing`.

Reproduced against the local `qa_testing_playground/store.py` application on 2026-09-22.
For an authenticated admin, submit a valid `POST /api/orders` payload but remove one of
`firstName`, `lastName`, `email`, `address`, or `country`.

Expected: HTTP 400 with an error identifying invalid/missing required data, without creating an order.
Actual on 2026-09-22: HTTP 201; an order was stored with an empty customer field. All five parameter cases failed.
The expectation follows the required customer fields in the checkout/release plan; the API at that time
implemented validation for items but not for those customer fields.

Resolution verified on 2026-09-25 against the local application: `create_api_order` now requires
all five customer fields to be nonempty strings, returns HTTP 400 with the invalid field names,
and trims valid values before storing the order. Non-object JSON request bodies also return HTTP 400.

The Chromium UI + API release run passed all 116 cases, including the original five failures.
Regression coverage additionally checks null, empty, whitespace, numeric, boolean, array and object
customer values; multiple invalid fields; trimmed stored values; and non-object request bodies.
Rejected customer-data requests are checked for absence of a created order. No tests are skipped
or marked expected-failure, and created test orders remain tracked for cleanup.

This verification covers the local source, not the deployed Render instance. The original
2026-09-22 failure above is retained as history; it no longer blocks the local release suite.
