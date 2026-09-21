Feature: Order Transaction
    Tests related to order transactions

  Scenario Outline: Verify Order success message shown in details page
    Given place the item order with <username> and <password>
    And the user is on the landing page
    When I login to portal with <username> and <password>
    And navigate to orders page
    And select the orderID
    Then order message is successfully displayed
    Examples:
      | username | password    |
      | tester   | password123 |