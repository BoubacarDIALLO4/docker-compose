import os
from pathlib import Path
from typing import Dict, List, Tuple

from tools.artifis_file_reader import get_zone_time_mapping_and_zones_per_seat_type, \
    get_transition_time, check_transition_points_zone_time_mapping_and_transition_time
from tools.ftp_client import FtpClient
from tools.trajectory_rules import TrajectoryRules
from tools.file import write_list_to_csv_file

PROGRAM_NUMBER_TO_NOT_STEAM = 99

KO_BUCKLE_STATE = 'KO'

RIGHT_BUCKLE = 'right_buckle'
CENTRAL_BUCKLE = 'central_buckle'
LEFT_BUCKLE = 'left_buckle'
UNKNOWN_BUCKLE_STATE = 'UNKNOWN'

ROBOT_OUTPUT_PATH = Path(__file__).absolute().parent / 'robot_output_folder'


class AbbCommunication:
    def __init__(self, my_logger, ip_ftp, port_ftp, user_ftp, password_ftp,
                 mounting_mode,
                 cycle_time, previous_transition_point, cumulated_time, acceptance_threshold,
                 zones_not_to_steam_from_buckle_detection, upload_ftp,
                 zone_time_mapping_file_path, transition_time_table_path,
                 orders_file_name, out_put_orders_directory) -> None:
        self.logger = my_logger
        self.ip_ftp = ip_ftp
        self.port_ftp = port_ftp
        self.user_ftp = user_ftp
        self.password_ftp = password_ftp
        self.mounting_mode = mounting_mode
        self.cycle_time = cycle_time
        self.previous_transition_point = previous_transition_point
        self.cumulated_time = cumulated_time
        self.acceptance_threshold = acceptance_threshold
        self.zones_not_to_steam_from_buckle_detection = zones_not_to_steam_from_buckle_detection
        self.upload_ftp = upload_ftp
        self.zone_time_mapping_file_path = zone_time_mapping_file_path
        self.transition_time_table_path = transition_time_table_path
        self.orders_file_name = orders_file_name
        self.orders_directory = out_put_orders_directory
        self.zone_time_mapping, self.zones_per_seat_type = get_zone_time_mapping_and_zones_per_seat_type(
            self.zone_time_mapping_file_path)
        self.transition_time_table = get_transition_time(self.transition_time_table_path)
        self.check_transition_points = check_transition_points_zone_time_mapping_and_transition_time(
            self.zone_time_mapping,
            self.transition_time_table)
        self.display_significant_check_transition_points_log_message(self.check_transition_points)

    def display_significant_check_transition_points_log_message(self, check_transition_points):
        if not check_transition_points:
            self.logger.warning("Zone_time_mapping file doesn't match with the transition_time file")
        else:
            self.logger.info("Zone_time_mapping file match with the transition_time file")

    def verify_buckle_belt_presence_and_remove_zones_if_necessary(self, predicted_wrinkles,
                                                                  buckle_belt_decision_result) -> Tuple[bool, Dict]:
        unknown_in_buckle_check = False

        if buckle_belt_decision_result:
            unknown_in_buckle_check = check_unknown_in_buckle_state_results(buckle_belt_decision_result)
            self.logger.info(f'Buckle detection : {buckle_belt_decision_result}')

            filtered_predicted_wrinkles = filter_out_steaming_zones_buckle_position_is_nok(
                predicted_wrinkles=predicted_wrinkles,
                buckle_detection=buckle_belt_decision_result,
                zones_not_to_steam_from_buckle_detection=self.zones_not_to_steam_from_buckle_detection)

            return unknown_in_buckle_check, filtered_predicted_wrinkles
        else:
            return unknown_in_buckle_check, predicted_wrinkles

    def upload_into_ftp_client(self, abb_format_zones: List) -> str:
        ftp_client = FtpClient(self.logger, orders_file_name=self.orders_file_name,
                               output_directory=self.orders_directory, ip_server=self.ip_ftp, port=self.port_ftp,
                               user=self.user_ftp, password=self.password_ftp)

        status = ftp_client.write_and_push_temporary_file_to_robot(zones=abb_format_zones)
        if status == 'FTP error':
            self.logger.warning('Error when uploading file on ABB FTP')

        return status

    def apply_calculate_robot_actions(self, original_predicted_wrinkles, wrinkles_succeed, buckle_belt_result, seat_info, serial_number):
        self.logger.info('apply abb communication')
        robot_decision = {}
        if seat_info:
            if wrinkles_succeed:
                try:
                    program_number = seat_info['program_number']
                    plant_project = seat_info['plant_project']
                    abb_format_zones = [
                        [program_number, serial_number, None, None, None, None, None, None, None, None, None]]
                    robot_decision.update(steaming_robot={'steaming': False,
                                                          'plant_project': plant_project,
                                                          'steaming_sequence_record': [],
                                                          'abb_format_zones': abb_format_zones,
                                                          'theoretical_working_time': 0,
                                                          'cycle_time': self.cycle_time,
                                                          'upload_ftp': False})

                    unknown_in_buckle_check, kept_predicted_wrinkles = \
                        self.verify_buckle_belt_presence_and_remove_zones_if_necessary(original_predicted_wrinkles,
                                                                                       buckle_belt_result)

                    if (int(program_number) != PROGRAM_NUMBER_TO_NOT_STEAM) and (
                            unknown_in_buckle_check is False):
                        cover_material = seat_info['cover_material']
                        trajectory_rule = TrajectoryRules(plant_project=plant_project,
                                                          acceptance_threshold=self.acceptance_threshold,
                                                          cover_material=cover_material,
                                                          zones_per_seat_type=self.zones_per_seat_type)

                        abb_format_zones, steaming_sequence_record, theoretical_working_time = \
                            trajectory_rule.define_zones_to_steam_in_abb_format_according_to_available_time(
                                predicted_wrinkles=kept_predicted_wrinkles,
                                zone_time_mapping=self.zone_time_mapping,
                                transition_time_table=self.transition_time_table,
                                cycle_time=self.cycle_time,
                                previous_transition_point=self.previous_transition_point,
                                cumulated_time=self.cumulated_time,
                                serial_number=serial_number,
                                program_number=program_number
                            )

                        if len(steaming_sequence_record) > 0:
                            robot_decision['steaming_robot']['steaming'] = True

                        else:
                            self.logger.info('No zones need to be steamed')

                        robot_decision['steaming_robot'].update({'abb_format_zones': abb_format_zones,
                                                                 'steaming_sequence_record': steaming_sequence_record,
                                                                 'theoretical_working_time': theoretical_working_time})

                    else:
                        self.logger.info('No steam treatment: Program not to steam or buckle_belt unknown state')

                    if self.upload_ftp:
                        if self.mounting_mode:
                            used_path = ROBOT_OUTPUT_PATH / self.orders_directory / self.orders_file_name
                            Path(ROBOT_OUTPUT_PATH / self.orders_directory).mkdir(parents=True, exist_ok=True)
                            self.logger.info(f' Path to use for copying order file: {used_path}')
                            status = write_list_to_csv_file(self.logger, abb_format_zones, used_path)
                        else:
                            status = self.upload_into_ftp_client(abb_format_zones)

                        if status == 'OK':
                            robot_decision['steaming_robot']['upload_ftp'] = True

                except Exception as e:
                    self.logger.error(
                        f'the error "{e}" occurred, the robot node is passed for this seat')
                    robot_decision.update(
                        steaming_robot={'state': 'error occurred, no information sent to robot',
                                        'steaming': False,
                                        'plant_project': 'not recognised',
                                        'steaming_sequence_record': [],
                                        'abb_format_zones': [],
                                        'theoretical_working_time': 0,
                                        'cycle_time': self.cycle_time,
                                        'upload_ftp': False})

            else:
                self.logger.info(
                    f'No wrinkles model correct result, does not produce csv file...')
                robot_decision.update(steaming_robot={'state': 'Wrinkles wrong result, no information sent to robot',
                                                      'steaming': False,
                                                      'steaming_sequence_record': [],
                                                      'abb_format_zones': [],
                                                      'theoretical_working_time': 0,
                                                      'cycle_time': self.cycle_time,
                                                      'upload_ftp': False})

        else:
            self.logger.error(
                f'No metadata recognised for seat "{serial_number}", node  abb skipped...')

            robot_decision.update(steaming_robot={'state': 'seat not recognised, no information sent to robot',
                                                  'steaming': False,
                                                  'plant_project': 'not recognised',
                                                  'steaming_sequence_record': [],
                                                  'abb_format_zones': [],
                                                  'theoretical_working_time': 0,
                                                  'cycle_time': self.cycle_time,
                                                  'upload_ftp': False})

        return robot_decision


def check_unknown_in_buckle_state_results(buckle_detection: Dict) -> bool:
    right_unknown_buckle = buckle_detection[RIGHT_BUCKLE] == UNKNOWN_BUCKLE_STATE
    left_unknown_buckle = buckle_detection[LEFT_BUCKLE] == UNKNOWN_BUCKLE_STATE
    central_unknown_buckle = buckle_detection[CENTRAL_BUCKLE] == UNKNOWN_BUCKLE_STATE

    if right_unknown_buckle or left_unknown_buckle or central_unknown_buckle:
        return True
    return False


def filter_out_steaming_zones_buckle_position_is_nok(predicted_wrinkles: Dict,
                                                     buckle_detection: Dict,
                                                     zones_not_to_steam_from_buckle_detection: Dict) -> Dict:
    bad_detections = []
    for key, value in buckle_detection.items():
        if value == KO_BUCKLE_STATE:
            bad_detections.append(key)

    if len(bad_detections) == 0:
        return predicted_wrinkles
    else:
        predicted_wrinkles_with_removed_zones = {}
        zones = []
        for bad_detection in bad_detections:
            zones.extend(zones_not_to_steam_from_buckle_detection[bad_detection])

        for predicted_wrinkle_zone, value in predicted_wrinkles.items():
            if predicted_wrinkle_zone not in zones:
                predicted_wrinkles_with_removed_zones[predicted_wrinkle_zone] = value
        return predicted_wrinkles_with_removed_zones
