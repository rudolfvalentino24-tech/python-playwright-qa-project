from pytest_bdd import when, then, scenario

@scenario("../features/authentication.feature", "AUTH-01 Admin logs in with valid credentials")
def test_AUTH_01():
    pass

@scenario("../features/authentication.feature", "AUTH-02 Login with invalid password is rejected")
def test_AUTH_02():
    pass

@scenario("../features/authentication.feature", "AUTH-03 Login with invalid username is rejected")
def test_AUTH_03():
    pass

@scenario("../features/authentication.feature", "AUTH-04 Login without accepting terms is rejected")
def test_AUTH_04():
    pass

@scenario("../features/authentication.feature", "AUTH-05 Logged-in user logs out successfully")
def test_AUTH_05():
    pass

@then("the admin should be logged in successfully")
def admin_is_logged_in(shared_data):
    shared_data["dashboard_page"].verifyLoginSuccessful()

@when("the admin logs in with an invalid password")
def admin_logs_in_with_invalid_password(admin_credentials, shared_data):
    invalid_password = admin_credentials["userPassword"] + "_invalid"
    shared_data["login_page"].submitLogin(admin_credentials["userEmail"], invalid_password)

@then("the login should be rejected")
def login_is_rejected(shared_data):
    shared_data["login_page"].verifyInvalidLogin()

@when("the user logs in with an invalid username")
def user_logs_in_with_invalid_username(admin_credentials, shared_data):
    invalid_username = "invalid_" + admin_credentials["userEmail"]
    shared_data["login_page"].submitLogin(invalid_username, admin_credentials["userPassword"])

@when("the admin enters valid credentials without accepting the terms")
def login_without_terms(admin_credentials, shared_data):
    shared_data["login_page"].loginWithoutTerms(
        admin_credentials["userEmail"], admin_credentials["userPassword"])

@then("the Terms validation message should be displayed")
def terms_validation_is_displayed(shared_data):
    shared_data["login_page"].verifyTermsValidation()

@when("the admin logs out")
def admin_logs_out_successfully(shared_data):
    shared_data["dashboard_page"].logout()

@then("the user should no longer be authenticated")
def user_is_not_authenticated(shared_data):
    shared_data["login_page"].verifySessionEnded()


