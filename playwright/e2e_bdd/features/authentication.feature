Feature: Authentication
  Tests related to user authentication

  Scenario: AUTH-01 Admin logs in with valid credentials
    Given the user is on the login page
    When the admin logs in with valid credentials
    Then the admin should be logged in successfully
    And the Store page should be displayed

  Scenario: AUTH-02 Login with invalid password is rejected
    Given the user is on the login page
    When the admin logs in with an invalid password
    Then the login should be rejected
    And the login page should be displayed

  Scenario: AUTH-03 Login with invalid username is rejected
    Given the user is on the login page
    When the user logs in with an invalid username
    Then the login should be rejected
    And the login page should be displayed

  Scenario: AUTH-04 Login without accepting terms is rejected
    Given the user is on the login page
    When the admin enters valid credentials without accepting the terms
    Then the Terms validation message should be displayed
    And the login page should be displayed

  Scenario: AUTH-05 Logged-in user logs out successfully
    Given the user is on the login page
    When the admin logs in with valid credentials
    And the admin logs out
    Then the login page should be displayed
    And the user should no longer be authenticated