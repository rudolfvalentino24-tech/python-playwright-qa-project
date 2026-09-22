Feature: Cart
  Tests related to adding, viewing and removing products from the cart

  Scenario: CART-01 Add one product to cart
    Given the admin is logged in
    When the admin adds a product to the cart
    And the admin opens the cart
    Then the selected product should be displayed in the cart

  Scenario: CART-02 Add multiple products to cart
    Given the admin is logged in
    When the admin adds multiple products to the cart
    And the admin opens the cart
    Then all selected products should be displayed in the cart

  Scenario: CART-03 Cart displays correct product information
    Given the admin has added a product to the cart
    When the admin opens the cart
    Then the correct product name should be displayed
    And the correct product price should be displayed

  Scenario: CART-04 Cart total is calculated correctly
    Given the admin has added multiple products to the cart
    When the admin opens the cart
    Then the cart total should equal the sum of the selected products

  Scenario: CART-05 Remove product from cart
    Given the admin has added multiple products to the cart
    When the admin opens the cart
    And the admin removes a product from the cart
    Then the removed product should no longer be displayed
    And the cart total should be updated

  Scenario: CART-06 Empty cart is displayed correctly
    Given the admin is logged in
    When the admin opens the cart
    Then the cart should be empty