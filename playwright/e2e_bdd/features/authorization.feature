Feature: authorization
  Tests related to user authorization

  Scenario: AUTH-06 Logged-out user cannot access the Store page
    Given the user is on the login page
    When the user tries to access the Store page without authentication
    Then the login page should be displayed