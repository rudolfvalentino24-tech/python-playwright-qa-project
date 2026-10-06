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

  Scenario: REL-UI-AUTH-02 Second admin logs in successfully
    Given the user is on the login page
    When the second admin logs in
    Then the Store page should be displayed

  Scenario Outline: <case_id> Missing <field> is validated
    Given the user is on the login page
    When the admin submits login without "<field>"
    Then the login page should be displayed
    And the login "<field>" field should be required

    Examples:
      | case_id        | field    |
      | REL-UI-AUTH-06 | Username |
      | REL-UI-AUTH-07 | Password |

  @regression @release
  Scenario: AUTH-PASSWORD-REVEAL-02 Reveal password icon is not shown when the password field is only focused
    Given the user is on the login page
    When the user focuses on the password field
    Then the reveal password icon should not be displayed

  @regression @release @smoke
  Scenario: AUTH-TERMS-01 User can open Terms & Conditions and return to login
    Given the user is on the login page
    When the user opens the Terms & Conditions
    Then the Terms & Conditions page should be displayed
    And the user returns to the login page

  @regression @release
  Scenario: AUTH-TERMS-02 Terms page displays QA training warning
    Given the user is on the login page
    When the user opens the Terms & Conditions
    Then the Terms & Conditions page should be displayed
    And the QA training warning should be displayed

  @regression @release
  Scenario: AUTH-PASSWORD-VIS-01 Password visibility toggle shows and hides password correctly
    Given the user is on the login page
    When the user enters "Test123!" in the password field
    Then the password should be masked
    When the user clicks the password visibility toggle
    Then the password should be visible
    And the password value should remain "Test123!"
    When the user clicks the password visibility toggle
    Then the password should be masked
    And the password value should remain "Test123!"

  @smoke @regression @release
  Scenario: AUTH-PASSWORD-VIS-02 Password visibility toggle does not interfere with login submission
    Given the user is on the login page
    And the user enters valid login credentials
    When the user clicks the password visibility toggle
    Then the login form should not be submitted
    And the login page should be displayed
    When the user submits the login form
    Then the Store page should be displayed

  @regression @release
  Scenario: AUTH-PASSWORD-VIS-03 Password visibility toggle supports keyboard interaction and preserves focus
    Given the user is on the login page
    And the user enters "Test123!" in the password field
    When the user navigates to the password visibility toggle using the keyboard
    Then the password visibility toggle should be focused
    When the user activates the password visibility toggle using the keyboard
    Then the password should be visible
    And the password visibility toggle should be focused

  @regression @release
  Scenario: AUTH-PASSWORD-VIS-04 Password visibility toggle exposes the correct accessible label
    Given the user is on the login page
    And the user enters "Test123!" in the password field
    Then the password visibility toggle accessible label should be "Show password"
    And the password visibility toggle should display "Show"
    And the password visibility toggle pressed state should be "false"
    When the user clicks the password visibility toggle
    Then the password visibility toggle accessible label should be "Hide password"
    And the password visibility toggle should display "Hide"
    And the password visibility toggle pressed state should be "true"
    When the user clicks the password visibility toggle
    Then the password visibility toggle accessible label should be "Show password"
    And the password visibility toggle should display "Show"
    And the password visibility toggle pressed state should be "false"

  @regression @release
  Scenario: AUTH-PASSWORD-VIS-05 Password visibility returns to hidden after reload or navigation
    Given the user is on the login page
    And the user enters "Test123!" in the password field
    And the user clicks the password visibility toggle
    Then the password should be visible
    And the password visibility toggle should display "Hide"
    And the password visibility toggle pressed state should be "true"
    When the user reloads the login page
    Then the password should be masked
    And the password visibility toggle should display "Show"
    And the password visibility toggle pressed state should be "false"
    When the user enters "Test123!" in the password field
    And the user clicks the password visibility toggle
    Then the password should be visible
    And the password visibility toggle should display "Hide"
    And the password visibility toggle pressed state should be "true"
    When the user leaves and returns to the login page
    Then the password should be masked
    And the password visibility toggle should display "Show"
    And the password visibility toggle pressed state should be "false"
