Feature: Order management
  Admins can delete orders and the deletion persists in Order History
  # ORDER-01 through ORDER-06 are covered by E2E-001 in storePurchase.feature.
  # See COVERAGE.md for the complete plan-to-test mapping.

  Background:
    Given the admin has added a product to the cart
    When the admin opens the cart
    And the admin proceeds to checkout
    And the admin enters valid checkout information
    And the admin places the order
    Then the order should be created successfully
    And an order number should be displayed
    When the admin navigates to order history
    Then the created order should appear in the order history

  Scenario: ORDER-07 Admin can delete an order from Order Details
    When the admin opens the created order
    Then the correct order number should be displayed
    When the admin deletes the order from Order Details and confirms
    Then the deleted order should not appear in Order History
    When the admin refreshes Order History
    Then the deleted order should not appear in Order History

  Scenario: ORDER-08 Order deleted from Order History stays removed after refresh
    When the admin deletes the created order from Order History and confirms
    Then the deleted order should not appear in Order History
    When the admin refreshes Order History
    Then the deleted order should not appear in Order History
