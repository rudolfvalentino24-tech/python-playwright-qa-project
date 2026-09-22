Feature: Store
  Tests related to the Store page and available products

  Scenario: STORE-01 Store page loads after admin login
    Given the user is on the login page
    When the admin logs in with valid credentials
    Then the Store page should be displayed

  Scenario: STORE-02 Products are displayed
    Given the admin is logged in
    Then the products should be displayed

  Scenario: STORE-03 Product information is displayed correctly
    Given the admin is logged in
    Then each product should display its name
    And each product should display its price
    And each product should have an Add to Cart button