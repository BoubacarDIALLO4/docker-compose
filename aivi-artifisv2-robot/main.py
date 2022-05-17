import json
import logging
import os
from pathlib import Path
import pandas as pd
import time
import uuid
import datetime
from ftplib import FTP
import pika
from azure.storage.blob import ContainerClient

from abb_communication import AbbCommunication
from tools.file import load_data_from_json_file
from prometheus_client import start_http_server, Summary, Counter

RIGHT_BUCKLE = 'right_buckle'
CENTRAL_BUCKLE = 'central_buckle'
LEFT_BUCKLE = 'left_buckle'


def retrieve_configuration_file_from_ftp_server(file_name, ftp_server_ip, used_port, used_user, used_password,
                                                destination_path):
    ftp_client = FTP()
    ftp_client.connect(ftp_server_ip, used_port)
    ftp_client.login(used_user, used_password)


def get_configuration_files():
    # retrieve_configuration_files_from_ftp_server()
    default_config_path = Path(__file__).absolute().parent / 'default_configuration'
    requested_config_path = Path(__file__).absolute().parent / 'requested_configuration'
    if os.path.isfile((requested_config_path / 'zone_time_mapping.csv').resolve().as_posix()):
        logger.info(f'Requested configuration taken for "zone_time_mapping.csv"')
        zone_time_mapping_file_path = (requested_config_path / 'zone_time_mapping.csv').resolve().as_posix()
    else:
        logger.info(f'Default configuration taken for "zone_time_mapping.csv"')
        zone_time_mapping_file_path = (default_config_path / 'zone_time_mapping.csv').resolve().as_posix()

    if os.path.isfile((requested_config_path / 'transition_time_table.csv').resolve().as_posix()):
        logger.info(f'Requested configuration taken for "transition_time_table.csv"')
        transition_time_table_file_path = (requested_config_path / 'transition_time_table.csv').resolve().as_posix()
    else:
        logger.info(f'Default configuration taken for "transition_time_table.csv"')
        transition_time_table_file_path = (default_config_path / 'transition_time_table.csv').resolve().as_posix()

    if os.path.isfile((requested_config_path / 'robot_module_configuration.json').resolve().as_posix()):
        logger.info(f'Requested configuration taken for "robot_module_configuration.json"')
        robot_module_configuration_file_path = (
                requested_config_path / 'robot_module_configuration.json').resolve().as_posix()
    else:
        logger.info(f'Default configuration taken for "robot_module_configuration.json"')
        robot_module_configuration_file_path = (
                default_config_path / 'robot_module_configuration.json').resolve().as_posix()

    return zone_time_mapping_file_path, transition_time_table_file_path, robot_module_configuration_file_path


def set_logs():
    logs_handler = logging.StreamHandler()
    logs_formatter = logging.Formatter('%(asctime)s %(levelname)-8s - %(message)s')
    logs_handler.setFormatter(logs_formatter)

    my_logger = logging.getLogger(__name__)
    my_logger.setLevel(os.getenv('LOG_LEVEL', logging.INFO))
    my_logger.addHandler(logs_handler)

    return my_logger


def initialize_amqp_connection(amqp_host, output_exchange, input_exchange, input_routing_key):
    logger.info(f'Connecting to AMQP host {amqp_host}...')
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=amqp_host))
    channel = connection.channel()

    logger.info(f'Declaring input exchange {input_exchange}...')
    channel.exchange_declare(exchange=input_exchange, exchange_type='topic')

    logger.info(f'Declaring temporary input queue...')
    input_queue = channel.queue_declare(queue='', exclusive=True).method.queue

    logger.info(f'Binding input queue "{input_queue}" to input exchange...')
    channel.queue_bind(exchange=input_exchange, queue=input_queue, routing_key=input_routing_key)

    logger.info(f'Declaring output exchange "{output_exchange}"...')
    channel.exchange_declare(exchange=output_exchange, exchange_type='topic')

    return channel, input_queue


def decode_input_message(logger, body):
    logger.info(" [x] Message Received")
    message = json.loads(body.decode())
    buckle_belt_result = message.get("decisions", {"decisions": ''}).get("front_buckle_belt_domain_decision")
    wrinkles_result = message.get("models")["wrinkle_detector"].get("predicted_acceptance_per_zone")
    wrinkles_succeed = message.get("models")["wrinkle_detector"].get("succeed")
    serial_number = message.get("metadata")["serial_number"]
    seat_info = message.get("metadata")["seat_info"]
    time_stamp = message.get("metadata", {"trigger_time": 0})["trigger_time"]

    return message, buckle_belt_result, wrinkles_result, wrinkles_succeed, serial_number, seat_info, time_stamp


def publish_output_message(logger, message, rabbit_mq_channel, rabbit_mq_output_exchange, robot_decision_result,
                           output_routing_key):
    logger.info("Publishing output message...")

    if "decisions" in message:
        message["decisions"].update(robot_decision_result)
    else:
        message.update({"decisions": robot_decision_result})

    body_message = json.dumps(message)
    rabbit_mq_channel.basic_publish(exchange=rabbit_mq_output_exchange, routing_key=output_routing_key,
                                    body=body_message)


def check_blob_container(logger, conn_str, container_name):
    container_client = ContainerClient.from_connection_string(
        conn_str=conn_str, container_name=container_name)
    try:
        logger.info(f"Verifying blob container '{container_name}'...")
        container_client.get_container_properties()
    except Exception as e:
        logger.warning(
            f"Container '{container_name}' does not exist. Creating...")
        container_client.create_container()

    return container_client


logger = set_logs()


def main():
    rabbit_mq_server_url = os.getenv('AMQP_HOST', 'localhost')
    input_ip_ftp = os.getenv("ROBOT_IP_ADDRESS", '127.0.0.1')
    input_port_ftp = int(os.getenv('ROBOT_PORT', 2121))
    input_user_ftp = os.getenv('FTP_USER', 'user')
    input_password_ftp = os.getenv('FTP_PASSWORD', 'password')
    mounting_mode = os.getenv('MOUNTING_MODE', 'False').lower() in 'true'

    ftp_server_out_put_directory = os.getenv('SERVER_OUTPUT_DIRECTORY', 'Aivi_Output')
    input_orders_file_name = os.getenv('INPUT_ORDER_FILE_NAME', 'orders.csv')
    rabbit_mq_output_exchange_name = os.getenv('OUTPUT_EXCHANGE', 'robot_output')
    rabbit_mq_input_exchange_name = os.getenv('INPUT_EXCHANGE', 'robot_input')
    blob_connection_string = os.environ["BLOB_STORAGE_CONNECTION_STRING"]
    blob_container_name = os.getenv('BLOB_CONTAINER_NAME', 'stlocal')
    input_routing_key = os.getenv("INPUT_ROUTING_KEY", "#")
    output_routing_key = os.getenv("OUTPUT_ROUTING_KEY", "")
    METRICS_PORT = int(os.getenv('METRICS_PORT', 9605))

    labels = ['deviceId', 'instanceNumber', 'iothubHostname', 'moduleId']
    deviceId = os.getenv('IOTEDGE_DEVICEID')
    instanceNumber = uuid.uuid4()
    iothubHostname = os.getenv('IOTEDGE_IOTHUBHOSTNAME')
    moduleId = os.getenv('IOTEDGE_MODULEID')
    summary_process = Summary(f"{moduleId}_summary_process", 'Process summary', labels).labels(
        deviceId, instanceNumber, iothubHostname, moduleId)
    counter_failures = Counter(f"{moduleId}_counter_failures", "Failure counter", labels).labels(
        deviceId, instanceNumber, iothubHostname, moduleId)

    logger.info('Starting up http server to expose metrics...')
    start_http_server(METRICS_PORT)

    input_zone_time_mapping_file_path, input_transition_time_table_path, input_robot_configuration_file_path = \
        get_configuration_files()

    robot_configuration_dict = load_data_from_json_file(input_robot_configuration_file_path, logger)
    input_previous_transition_point = robot_configuration_dict["previous_transition_point"]
    input_cycle_time = float(robot_configuration_dict["cycle_time"])
    input_cumulated_time = float(robot_configuration_dict["cumulated_time"])
    input_acceptance_threshold = int(robot_configuration_dict["acceptance_threshold"])
    input_upload_ftp = robot_configuration_dict["upload_ftp"]
    input_left_buckle = robot_configuration_dict.get("left_buckle")
    input_central_buckle = robot_configuration_dict.get("central_buckle")
    input_right_buckle = robot_configuration_dict.get("right_buckle")
    input_zones_not_to_steam_from_buckle_detection = {LEFT_BUCKLE: input_left_buckle,
                                                      CENTRAL_BUCKLE: input_central_buckle,
                                                      RIGHT_BUCKLE: input_right_buckle}

    rabbit_mq_channel, input_queue = initialize_amqp_connection(rabbit_mq_server_url, rabbit_mq_output_exchange_name,
                                                                rabbit_mq_input_exchange_name, input_routing_key)

    robot_instance = AbbCommunication(logger, input_ip_ftp, input_port_ftp, input_user_ftp, input_password_ftp,
                                      mounting_mode,
                                      input_cycle_time, input_previous_transition_point, input_cumulated_time,
                                      input_acceptance_threshold,
                                      input_zones_not_to_steam_from_buckle_detection, input_upload_ftp,
                                      input_zone_time_mapping_file_path, input_transition_time_table_path,
                                      input_orders_file_name, ftp_server_out_put_directory)

    container_client = check_blob_container(logger, blob_connection_string, blob_container_name)

    @summary_process.time()
    @counter_failures.count_exceptions()
    def callback(rbmq_ch, method, properties, body):
        message, buckle_belt_result, wrinkles_result, wrinkles_succeed, serial_number, seat_info, timestamp = \
            decode_input_message(logger, body)
        tic = time.perf_counter()
        robot_decision_result = robot_instance.apply_calculate_robot_actions(wrinkles_result, wrinkles_succeed, buckle_belt_result,
                                                                             seat_info, serial_number)

        if robot_decision_result['steaming_robot']['upload_ftp']:
            time_stamp = datetime.datetime.fromisoformat(timestamp)
            year = time_stamp.year
            month = f'{time_stamp.month:02}'
            day = f'{time_stamp.day:02}'

            plant_id = message["metadata"]["station_info"]["plant"]
            country_id = message["metadata"]["station_info"]["country"]
            station_id = message["metadata"]["station_info"]["station_full_id"]
            pipeline_id = message["metadata"]["pipeline_id"]
            blob_name = f'raw/{country_id}_{plant_id}/{station_id}/{year}/{month}/{day}/{pipeline_id}_robot_orders.csv'

            result_put_in_orders = robot_decision_result['steaming_robot']['abb_format_zones']
            df = pd.DataFrame(result_put_in_orders)
            output = df.to_csv(index=False, encoding="utf-8", header=None)
            container_client.upload_blob(name=blob_name, data=output, overwrite=True)

        publish_output_message(logger, message, rabbit_mq_channel,
                               rabbit_mq_output_exchange_name, robot_decision_result, output_routing_key)
        toc = time.perf_counter()
        logger.info(f'Done in {toc - tic:0.4f} seconds.')

    rabbit_mq_channel.basic_consume(queue=input_queue, on_message_callback=callback, auto_ack=True)

    logger.info(' [*] Waiting for messages. To exit press CTRL+C')
    rabbit_mq_channel.start_consuming()


if __name__ == "__main__":
    main()
