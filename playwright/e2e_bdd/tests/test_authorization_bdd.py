from pytest_bdd import when, scenario

@scenario("../features/authorization.feature", "AUTH-06 Logged-out user cannot access the Store page")
def test_AUTH_06():
    pass

@when("the user tries to access the Store page without authentication")
def user_accesses_store_without_authentication(shared_data):
    shared_data["login_page"].openProtectedStorePage()