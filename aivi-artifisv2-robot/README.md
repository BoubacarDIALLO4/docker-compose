# Introduction 
This is the robot artifis module. Its aim is to extract the wrinkles results produced by the wrinkles module, 
processes them by the priority order of the seat zones, according to the available time for the robot. Finally, the 
concerned seat zones are sent in a file to the robot to steam the seat. 

In order to perform this function, the module needs the result of the wrinkles module, the metadata of the concerned 
seat, and the robot configuration files to process that seat.
This information is given by the out_put of the wrinkles module.

## Run integration test

````bash
docker-compose down; \
docker-compose build && \
docker-compose run integration_tests
````


## Build docker image and run locally

Run the following bash script

```bash
docker-compose up --build
```

# Required files 
In order to execute the module, we need the following files:
"transition_time_mapping.csv", "zone_time_mapping.csv" and "robot_module_configuration.json"

The content of "robot_module_configuration.json" should be as follows:
```json
{
    "cycle_time": 59,
    "previous_transition_point": "PDEFAULT",
    "cumulated_time": 2.488,
    "acceptance_threshold": 1,
    "left_buckle": ["8", "9"],
    "central_buckle": ["27", "28"],
    "right_buckle": ["3", "8"],
    "upload_ftp": true

}
```
The meaning of the keys in the previous file is as the following:
- "cycle_time": is the total time that robot obtains to steam the seat (containing moving to different zones),
- "previous_transition_point": is the first position of the robot at the starting operation,
- "cumulated_time": is the initial time value that should be subtracted from the "cycle time" since the beginning,
- "acceptance_threshold": is the wrinkles acceptance threshold value under which the steam should be performed,
- "left_buckle", "central_buckle" and "right_buckle": are the zones to which the different buckles belong.
    This is to avoid steaming their zones when the buckles are out of their holes to not burn them.
- "upload_ftp": to indicate that the upload of the "orders.csv" file to the robot FTP is demanded.


# model format of input message
In order to test the functioning of the module, the input message through rabbit_mq should contain the following information:
```json
{
   "metadata":{
      "station_info":{
         "country":"FR",
         "plant":"ETL",
         "line_id":"LINE1",
         "station_full_id":"FRETLSTATION1"
      },
      "barcode":"G48024127B1010010111000011F100010002000210001000004221000R3000000000000001110100000000000K0A000C00000ER1R080F0FG00266661",
      "serial_number":"G4802412",
      "trigger_time":"2022-03-25T05:10:23.234+00:00",
      "pipeline_id":"FRETLSTATION1_G4802412_20220325-051023",
      "barcode_seen":false,
      "seat_info":{
         "id":"ER",
         "project":"R8",
         "plant_project":"R8",
         "variant":"BK2_MECA",
         "training_scope":"R8_Tissu_Tep",
         "seat_position":"left",
         "cover_material":"Tissu_Tep",
         "zoning_template_id":"BK2_MECA_left",
         "wrinkles_threshold_id":"",
         "program_number":"473"
      }
   },
   "models":{
      "wrinkle_detector":{
        "succeed": "true",
         "predicted_acceptance_per_zone":{
            "10":0,
            "31":0,
            "50":0
         }
      }
   }
}
```
The timestamp represent the arrival time of the seat barcode to the application. It has the format:
yyyymmdd-hhmmss

# output format 
The robot module produces as an output an "orders.csv" to be uploaded to the blob storage and also sent to the robot FTP,
it has the following format:

```json
{
  "metadata": {
    "station_info": {
      "country": "FR",
      "plant": "ETL",
      "line_id": "LINE1",
      "station_full_id": "FRETLSTATION1"
    },
    "barcode": "G48024127B1010010111000011F100010002000210001000004221000R3000000000000001110100000000000K0A000C00000ER1R080F0FG00266661",
    "serial_number": "G4802412",
    "trigger_time": "2022-03-25T05:10:23.234+00:00",
    "pipeline_id": "FRETLSTATION1_G4802412_20220325-051023",
    "barcode_seen": "false",
    "seat_info": {
      "id": "ER",
      "project": "R8",
      "plant_project": "R8",
      "variant": "BK2_MECA",
      "training_scope": "R8_Tissu_Tep",
      "seat_position": "left",
      "cover_material": "Tissu_Tep",
      "zoning_template_id": "BK2_MECA_left",
      "wrinkles_threshold_id": "",
      "program_number": "473"
    }
  },
  "models": {
    "wrinkle_detector": {
      "predicted_acceptance_per_zone": {
        "10": 0,
        "31": 0,
        "50": 0
      }
    }
  },
  "decisions": {
    "steaming_robot": {
      "steaming": true,
      "plant_project": "R8",
      "steaming_sequence_record": [
        {
          "input_zone": 10,
          "acceptance_threshold": 0,
          "transition points": "HOME BL",
          "transition_time": 6.466,
          "steaming_time": 5.4
        },
        {
          "input_zone": 31,
          "acceptance_threshold": 0,
          "transition points": "BL BL",
          "transition_time": 0.0,
          "steaming_time": 3.79
        },
        {
          "input_zone": 50,
          "acceptance_threshold": 0,
          "transition points": "BL CM",
          "transition_time": 2.32,
          "steaming_time": 4.08
        }
      ],
      "abb_format_zones": [
        [
          "473",
          "G4802412",
          "",
          "",
          "",
          "",
          "",
          "",
          "",
          "",
          "",
          ""
        ],
        [
          "1",
          "10",
          "10",
          "1",
          "20",
          "0",
          "0",
          "0",
          "0",
          "0",
          "0"
        ],
        [
          "2",
          "31",
          "10",
          "1",
          "20",
          "0",
          "0",
          "0",
          "0",
          "0",
          "0"
        ],
        [
          "3",
          "50",
          "10",
          "1",
          "20",
          "0",
          "0",
          "0",
          "0",
          "0",
          "0"
        ]
      ],
      "theoretical_working_time": 22.1,
      "cycle_time": 48.0,
      "upload_ftp": true
    }
  }
}
```