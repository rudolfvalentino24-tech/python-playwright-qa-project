Feature: Session
  Authentication persists during navigation and ends after logout

  Scenario: SESSION-01 Session and cart persist while navigating
    Given the admin has added a product to the cart
    When the admin opens the cart
    Then the cart should retain the selected product
    When the admin proceeds to checkout
    Then the checkout page should be displayed
    When the admin visits Order History
    Then Order History should load successfully
    When the admin returns to the cart
    Then the cart should retain the selected product

  Scenario Outline: SESSION-02 Logout blocks access to <area>
    Given an order exists for permission checks
    And the admin is logged in
    When the admin opens Order History from the Store
    And the user logs out from Order History
    Then the login page should be displayed
    When the logged-out user opens "<area>"
    Then the login page should be displayed

    Examples:
      | area          |
      | Store         |
      | Cart          |
      | Checkout      |
      | Order History |
      | Order Details |
