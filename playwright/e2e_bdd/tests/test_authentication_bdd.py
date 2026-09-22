from pytest_bdd import parsers, when, then, scenarios

scenarios("../features/authentication.feature")

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


@when(parsers.parse('the admin submits login without "{field}"'))
def admin_submits_missing_login_field(admin_credentials, shared_data, field):
    username = "" if field == "Username" else admin_credentials["userEmail"]
    password = "" if field == "Password" else admin_credentials["userPassword"]
    shared_data["login_page"].submitLogin(username, password)


@then(parsers.parse('the login "{field}" field should be required'))
def login_field_is_required(shared_data, field):
    shared_data["login_page"].verifyRequiredField(field)


