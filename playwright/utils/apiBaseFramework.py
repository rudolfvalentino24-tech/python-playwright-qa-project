from playwright.sync_api import BrowserContext, Playwright

from utils.config import storeURL


ordersPayload = {
    "firstName": "test",
    "lastName": "test",
    "email": "rudolfvalentino24@gmail.com",
    "address": "Test Address",
    "country": "AT",
    "items": [
        {"productId": 1, "quantity": 1},
        {"productId": 6, "quantity": 1},
    ],
}


class APIUtils:

    @staticmethod
    def _login_form(user_credentials):
        return {
            "username": user_credentials["userEmail"],
            "password": user_credentials["userPassword"],
            "terms": "on",
        }

    def getToken(self, playwright: Playwright, user_credentials):
        """Authenticate through an isolated API context and return a bearer token."""
        api_request_context = playwright.request.new_context(base_url=storeURL)

        try:
            response = api_request_context.post(
                "/login",
                form=self._login_form(user_credentials),
            )

            assert response.ok, response.text()

            token = response.json()["token"]
            print(f"Token: {token}")
            return token
        finally:
            api_request_context.dispose()

    def getTokenForBrowserContext(
        self,
        browser_context: BrowserContext,
        user_credentials,
    ):
        """
        Authenticate using the browser context's request API.

        The response cookie is stored in the same BrowserContext, so protected
        Flask pages can be opened while the returned bearer token is also
        available for localStorage/API calls.
        """
        response = browser_context.request.post(
            f"{storeURL}/login",
            form=self._login_form(user_credentials),
        )

        assert response.ok, response.text()

        token = response.json()["token"]
        print(f"Token: {token}")
        return token

    def createOrder(self, playwright: Playwright, user_credentials):
        token = self.getToken(playwright, user_credentials)
        api_request_context = playwright.request.new_context(base_url=storeURL)

        try:
            response = api_request_context.post(
                "/api/orders",
                data=ordersPayload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

            print(f"Status: {response.status}")
            print(f"Response: {response.text()}")
            assert response.ok, response.text()

            order_id = response.json()["orderId"]
            print(f"Order ID: {order_id}")
            return order_id
        finally:
            api_request_context.dispose()
