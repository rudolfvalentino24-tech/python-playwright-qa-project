from pytest_bdd import given, when, then, scenarios
from pageObjects.login import LoginPage

scenarios("../features/storePurchase.feature")

@given("the admin is on the login page")
def admin_on_login_page(browserInstance, shared_data):

    login_page = LoginPage(browserInstance)
    login_page.navigate()
    login_page.verifyLoginPage()
    shared_data["login_page"] = login_page

@when("the admin logs in")
def admin_logs_in(admin_credentials, shared_data):

    shared_data["dashboard_page"] = shared_data["login_page"].login(
        admin_credentials["userEmail"],
        admin_credentials["userPassword"]
    )

@then("the correct product should be displayed")
def verify_product(shared_data):

    shared_data["details_page"].verifyProduct(shared_data["product"])

@then("the correct customer information should be displayed")
def verify_customer(e2e_checkout_data, shared_data):

    shared_data["details_page"].verifyCustomer(e2e_checkout_data["customer"])

@then("the correct total should be displayed")
def verify_total(shared_data):

    shared_data["details_page"].verifyTotal(shared_data["total"])
