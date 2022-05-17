Feature: Sad happy path test robot module

  Scenario: Wrinkles false,  don't upload the csv files in the ftp server
    Given module is running
    When receive message but wrinkle not succeed
    Then wait 5 seconds
    Then should publish a message, csv file not send to the robot