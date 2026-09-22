Feature: Checkout
  Validate checkout information and totals before creating an order

  Scenario Outline: CHECK-03 Required customer fields are validated
    Given the admin has added a product to the cart
    When the admin opens the cart
    And the admin proceeds to checkout
    And the admin enters valid checkout information
    And the admin leaves the "<field>" checkout field empty
    And the admin attempts to place the order
    Then the checkout submission should be blocked
    And the "<field>" checkout field should be required

    Examples:
      | field      |
      | first name |
      | last name  |
      | email      |
      | address    |
      | country    |

  Scenario Outline: CHECK-03 Required payment fields are validated
    Given the admin has added a product to the cart
    When the admin opens the cart
    And the admin proceeds to checkout
    And the admin enters valid checkout information
    And the admin leaves the "<field>" checkout field empty
    And the admin attempts to place the order
    Then the checkout submission should be blocked
    And the "<field>" checkout field should be required

    Examples:
      | field           |
      | cardholder name |
      | card number     |
      | expiry          |
      | CVV             |

  Scenario: CHECK-03 Order confirmation is required
    Given the admin has added a product to the cart
    When the admin opens the cart
    And the admin proceeds to checkout
    And the admin enters valid checkout information
    And the admin unchecks the order confirmation
    And the admin attempts to place the order
    Then the checkout submission should be blocked
    And the "order confirmation" checkout field should be required

  Scenario: CHECK-04 Checkout total matches the cart and selected products
    Given the admin has added multiple products to the cart
    When the admin opens the cart
    Then the cart total should match the selected product prices
    When the admin proceeds to checkout
    Then the checkout page should be displayed
    And the checkout total should match the cart total
    And the checkout total should equal the sum of the selected product prices

  Scenario: CHECK-06 Invalid email is rejected
    Given the admin has added a product to the cart
    When the admin opens the cart
    And the admin proceeds to checkout
    And the admin enters valid checkout information
    And the admin enters "invalid-email" as the checkout email
    And the admin attempts to place the order
    Then the checkout submission should be blocked
    And the checkout email should be invalid
