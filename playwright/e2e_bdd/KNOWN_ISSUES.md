# Findings from the remaining Store strategy tests

## API accepts orders without required customer data

Plan reference: REL-API-ORD-09 (missing required order data).
Test: `playwright/api/test_store_api.py::test_required_order_data_is_rejected_when_missing`.

Reproduced against the local `qa_testing_playground/store.py` application on 2026-09-22.
For an authenticated admin, submit a valid `POST /api/orders` payload but remove one of
`firstName`, `lastName`, `email`, `address`, or `country`.

Expected: HTTP 400 with an error identifying invalid/missing required data, without creating an order.
Actual: HTTP 201; an order is stored with an empty customer field. All five parameter cases fail.
The expectation follows the required customer fields in the checkout/release plan; the current API
implements validation for items but not for those customer fields.

The new tests deliberately remain failing (no skip/xfail) so a release run reports the gap.
Created orders are tracked and cleaned up even when the assertions fail. No application code was
changed as part of adding test coverage. The browser's required-field validation passes and does
not compensate for this server-side gap.
