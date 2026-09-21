from playwright.sync_api import Playwright

from conftest import user_credentials
from utils.config import storeURL

ordersPayload = {
    "firstName": "test",
    "lastName": "test",
    "email": "rudolfvalentino24@gmail.com",
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

class APIUtils:

    def getToken(self, playwright:Playwright, user_credentials):
        user_name = user_credentials['userEmail']
        user_password = user_credentials['userPassword']
        api_request_context = playwright.request.new_context(base_url=storeURL)
        response = api_request_context.post("/login",
                                            form = {
                                                "username": user_name,
                                                "password": user_password,
                                                "terms": "on"
            }
        )

        assert  response.ok
        response_body = response.json()
        token = response_body["token"]
        print(f"Token: {token}")
        return token

    def createOrder(self, playwright:Playwright, user_credentials):

        token = self.getToken(playwright, user_credentials)
        api_request_context = playwright.request.new_context(base_url=storeURL)
        response = api_request_context.post("/api/orders",
                                 data = ordersPayload,
                                 headers = {"Authorization": f"Bearer {token}",
                                            "Content-type": "application/json"
                                            })

        print(f"Status: {response.status}")
        print(f"Response: {response.text()}")
        assert response.ok, response.text()
        response_json = response.json()
        order_id = response_json["orderId"]
        print(f"Order ID: {order_id}")
        return order_id