from playwright.sync_api import Playwright

from utils.apiBaseFramework import APIUtils
from utils.config import storeURL


def test_token_expired(playwright: Playwright, admin_credentials):
    api_utils = APIUtils()

    # 1. Get a valid token using credentials from credentials.json.
    token = api_utils.getToken(playwright, admin_credentials)

    api_request_context = playwright.request.new_context(base_url=storeURL)

    try:
        # 2. Verify the token works first.
        valid_response = api_request_context.get(
            "/api/user",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert valid_response.status == 200
        assert valid_response.json()["username"] == admin_credentials["userEmail"]

        # 3. Force the token to expire.
        expire_response = api_request_context.post(
            "/api/test/expire-token",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert expire_response.status == 200

        # 4. Try to use the same token again.
        expired_response = api_request_context.get(
            "/api/user",
            headers={"Authorization": f"Bearer {token}"},
        )

        # 5. The expired token must be rejected.
        assert expired_response.status == 401
        assert expired_response.json()["error"] == "Token expired"

        print(expired_response.json())
    finally:
        api_request_context.dispose()
