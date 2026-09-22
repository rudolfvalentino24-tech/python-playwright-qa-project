Feature: Store purchase
    Critical end-to-end purchase journeys

  Scenario: Admin completes purchase successfully
    Given the admin is on the login page
    When the admin logs in
    And the admin adds a product to the cart
    And the admin opens the cart
    And the admin proceeds to checkout
    And the admin enters valid checkout information
    And the admin places the order
    Then the order should be created successfully
    And an order number should be displayed
    When the admin navigates to order history
    Then the created order should appear in the order history
    When the admin opens the created order
    Then the correct order number should be displayed
    And the correct product should be displayed
    And the correct customer information should be displayed
    And the correct total should be displayed