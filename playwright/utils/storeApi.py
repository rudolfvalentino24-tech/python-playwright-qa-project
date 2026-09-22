class StoreAPI:
    """Isolated authenticated API client; tracks created orders for fixture cleanup."""

    def __init__(self, request, credentials):
        self.request = request
        self.order_ids = []
        response = request.post("/login", form={
            "username": credentials["userEmail"],
            "password": credentials["userPassword"],
        })
        assert response.status == 200, "API login failed"
        self.identity = response.json()
        assert self.identity["username"] == credentials["userEmail"]
        self.token = self.identity["token"]
        assert isinstance(self.token, str) and self.token
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def getUser(self):
        return self.request.get("/api/user", headers=self.headers)

    def getOrders(self):
        return self.request.get("/api/orders", headers=self.headers)

    def createOrder(self, payload):
        response = self.request.post("/api/orders", data=payload, headers=self.headers)
        if response.status == 201:
            self.order_ids.append(response.json()["orderId"])
        return response

    def expireToken(self):
        response = self.request.post("/api/test/expire-token", headers=self.headers)
        assert response.status == 200

    def deleteOrder(self, order_id):
        return self.request.post(f"/orders/{order_id}/delete", max_redirects=0)
