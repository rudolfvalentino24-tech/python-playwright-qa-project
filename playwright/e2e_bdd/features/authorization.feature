Feature: authorization
  Tests related to user authorization

  Scenario: AUTH-06 Logged-out user cannot access the Store page
    Given the user is on the login page
    When the user tries to access the Store page without authentication
    Then the login page should be displayed

  @smoke
  Scenario: ROLE-01 Orders viewer can access Order History
    Given the user is on the login page
    When the orders viewer logs in
    Then Order History should be displayed for the viewer

  Scenario: ROLE-02 Orders viewer can view Order Details
    Given an order exists for permission checks
    And the orders viewer is logged in
    When the viewer opens the created order
    Then the correct order number should be displayed
    And the viewer should see the purchased items and total

  @smoke
  Scenario Outline: <case_id> Orders viewer cannot access <area>
    Given the orders viewer is logged in
    When the viewer opens the protected "<area>" page
    Then Order History should be displayed for the viewer

    Examples:
      | case_id | area     |
      | ROLE-03 | Store    |
      | ROLE-04 | Cart     |
      | ROLE-05 | Checkout |

  Scenario: ROLE-07 Orders viewer has no order deletion controls
    Given an order exists for permission checks
    And the orders viewer is logged in
    Then the created order should appear in the order history
    And Order History should offer no admin controls
    When the viewer opens the created order
    Then Order Details should offer no deletion control

  Scenario: REL-UI-ORD-09 A second admin can see an order created by the first admin
    Given an order exists for permission checks
    And the user is on the login page
    When the second admin logs in
    And the admin opens Order History from the Store
    Then the created order should appear in the order history
    When the admin opens the created order
    Then the correct order number should be displayed
