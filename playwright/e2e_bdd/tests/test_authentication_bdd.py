from pytest_bdd import given, parsers, when, then, scenarios

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

@when("the user opens the Terms & Conditions")
def user_opens_terms(shared_data):
    shared_data["login_page"].openTermsAndConditions()


@then("the Terms & Conditions page should be displayed")
def terms_page_is_displayed(shared_data):
    shared_data["login_page"].verifyTermsAndConditionsPage()


@then("the user returns to the login page")
def user_returns_to_login(shared_data):
    shared_data["login_page"].returnToLoginPage()


@then("the QA training warning should be displayed")
def qa_training_warning_is_displayed(shared_data):
    # Verify that the QA training warning is displayed on the Terms page
    shared_data["login_page"].verifyQATrainingWarning()


@given("the user enters valid login credentials")
def user_enters_valid_login_credentials(admin_credentials, shared_data):
    shared_data["login_page"].enterLoginCredentials(
        admin_credentials["userEmail"],
        admin_credentials["userPassword"],
    )


@then("the login form should not be submitted")
def login_form_should_not_be_submitted(shared_data):
    shared_data["login_page"].verifyLoginFormNotSubmitted()


@when("the user submits the login form")
def user_submits_login_form(shared_data):
    shared_data["dashboard_page"] = shared_data["login_page"].submitLoginForm()


@when("the user navigates to the password visibility toggle using the keyboard")
def user_navigates_to_password_visibility_toggle_using_keyboard(shared_data):
    shared_data["login_page"].navigateToPasswordVisibilityToggleUsingKeyboard()


@then("the password visibility toggle should be focused")
def password_visibility_toggle_should_be_focused(shared_data):
    shared_data["login_page"].verifyPasswordVisibilityToggleFocused()


@when("the user activates the password visibility toggle using the keyboard")
def user_activates_password_visibility_toggle_using_keyboard(shared_data):
    shared_data["login_page"].activatePasswordVisibilityToggleUsingKeyboard()


@then(parsers.parse('the password visibility toggle accessible label should be "{label}"'))
def password_visibility_toggle_accessible_label_should_be(shared_data, label):
    shared_data["login_page"].verifyPasswordVisibilityToggleAccessibleLabel(label)


@then(parsers.parse('the password visibility toggle should display "{text}"'))
def password_visibility_toggle_should_display(shared_data, text):
    shared_data["login_page"].verifyPasswordVisibilityToggleText(text)


@then(parsers.parse('the password visibility toggle pressed state should be "{pressed}"'))
def password_visibility_toggle_pressed_state_should_be(shared_data, pressed):
    shared_data["login_page"].verifyPasswordVisibilityTogglePressedState(pressed)


@when("the user reloads the login page")
def user_reloads_login_page(shared_data):
    shared_data["login_page"].reloadLoginPage()


@when("the user leaves and returns to the login page")
def user_leaves_and_returns_to_login_page(shared_data):
    shared_data["login_page"].leaveAndReturnToLoginPage()
