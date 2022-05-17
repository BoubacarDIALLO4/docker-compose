import json
import time
import sys
from behave import *
from ftplib import FTP, all_errors
from typing import List


@given('module is running')
def step_impl(context):
    pass


@when('receive message')
def step_impl(context):
    input_message = json.dumps({
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
                    "succeed": "true",
                    "predicted_acceptance_per_zone": {
                        "10": 0,
                        "31": 0,
                        "50": 0
                    }
                }
            }



    })

    context.channel.basic_publish(exchange='ROBOT_INPUT',
                                  routing_key='whatever',
                                  body=input_message)

###
@when('receive message but wrinkle not succeed')
def step_impl(context):
    input_message = json.dumps({
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
        }

    })

    context.channel.basic_publish(exchange='ROBOT_INPUT',
                                  routing_key='whatever',
                                  body=input_message)


##

@then('wait {wait_seconds} seconds')
def wait(context, wait_seconds):
    time.sleep(float(wait_seconds))

@then('should publish a message')
def assert_check_output_robot_message(context):
    method_frame, header_frame, body = context.channel.basic_get(context.output_queue)
    assert method_frame is not None
    output_message = json.loads(body.decode())

    print('Published message:')
    print(json.dumps(output_message, indent=4))

    assert 'decisions' in output_message
    assert 'steaming_robot' in output_message["decisions"]
    assert 'upload_ftp' in output_message['decisions']['steaming_robot']
    assert output_message['decisions']['steaming_robot']['upload_ftp'] == True

@then('Check if the csv files is on ftp server')
def assert_check_csv_files_on_ftp_server(context):
    ftp = FTP('ftp_server')
    ftp.login('guest', 'guest')
    files_in_ftp = []
    ftp.cwd('/')
    ftp.retrlines('LIST', lambda line: files_in_ftp.append(line.split()[-1]))

    assert 'orders.csv' in files_in_ftp

##
@then('should publish a message, csv file not send to the robot')
def assert_check_output_robot_message(context):
    method_frame, header_frame, body = context.channel.basic_get(context.output_queue)
    assert method_frame is not None
    output_message = json.loads(body.decode())

    print('Published message:')
    print(json.dumps(output_message, indent=4))

    assert 'decisions' in output_message
    assert 'steaming_robot' in output_message["decisions"]
    assert 'upload_ftp' in output_message['decisions']['steaming_robot']
    assert output_message['decisions']['steaming_robot']['upload_ftp'] == False
