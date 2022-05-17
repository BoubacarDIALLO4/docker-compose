Feature: happy path test robot module

  Scenario: Upload the csv files in the ftp server
    Given module is running
    When receive message
    Then wait 5 seconds
    Then should publish a message
    Then Check if the csv files is on ftp server