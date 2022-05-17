import logging

from collections import namedtuple
from typing import List, Dict
from tools.artifis_file_reader import ZoneDescriptorKey, TransitionDescriptor, ZoneDescriptorValue

ZonePredictionProps = namedtuple('ZonePredictionProps', ['zone', 'acceptance'])
DEFAULT_TRAJECTORY_RULES_PARAMETERS = {
    'SPEED': '10',
    'STEAM': '0',
    'PRESSURE': '20',
    'INPUT_OFFSET_X': '0',
    'INPUT_OFFSET_Y': '0',
    'INPUT_OFFSET_Z': '50',
    'OUTPUT_OFFSET_X': '0',
    'OUTPUT_OFFSET_Y': '0',
    'OUTPUT_OFFSET_Z': '50',
    'TRAJECTORY_OCCURENCE': '1'

}


class TrajectoryRules:
    def __init__(self, zones_per_seat_type: Dict[str, List], plant_project: str, acceptance_threshold: int,
                 cover_material: str):
        """
        default parameters in robot inputs
        SPEED : robot speed
        STEAM : is the steam on (1) or off (0)
        PRESSURE : in Newton
        INPUT_OFFSET : shift in input
        OUTPUT_OFFSET : shift in output
        """

        self.default_parameters = DEFAULT_TRAJECTORY_RULES_PARAMETERS
        self.zones_per_seat_type = zones_per_seat_type
        self.plant_project = plant_project
        self.acceptance_threshold = acceptance_threshold
        self.cover_material = cover_material

    def get_default_parameters(self) -> List:
        return [self.default_parameters['SPEED'],
                self.default_parameters['STEAM'],
                self.default_parameters['PRESSURE'],
                self.default_parameters['INPUT_OFFSET_X'],
                self.default_parameters['INPUT_OFFSET_Y'],
                self.default_parameters['INPUT_OFFSET_Z'],
                self.default_parameters['OUTPUT_OFFSET_X'],
                self.default_parameters['OUTPUT_OFFSET_Y'],
                self.default_parameters['OUTPUT_OFFSET_Z'],
                self.default_parameters['TRAJECTORY_OCCURENCE']
                ]

    def sort_zones_according_to_zone_time_mapping(self, unsorted_zones_meta: List[ZonePredictionProps]) \
            -> List[ZonePredictionProps]:

        sorted_zones = []
        try:
            sorted_zones_per_priority_for_plant_project_seat_type = self.zones_per_seat_type[self.plant_project]

            list_sorted_unique_zones_per_seat_type = list(
                dict.fromkeys(sorted_zones_per_priority_for_plant_project_seat_type))

        except KeyError:
            logging.error(f'sort_zones_time_mapping_cycle : Not found the key : {self.plant_project}')
            list_sorted_unique_zones_per_seat_type = []

        for current_zone_to_match in list_sorted_unique_zones_per_seat_type:
            for zone_meta in unsorted_zones_meta:
                if int(zone_meta.zone) == int(current_zone_to_match):
                    sorted_zones.append(zone_meta)
        return sorted_zones

    @staticmethod
    def get_wrinkles_with_zone_and_acceptance(predicted_wrinkles: Dict) -> List[ZonePredictionProps]:
        wrinkles_with_zone = []
        for predicted_zone, real_acceptance in predicted_wrinkles.items():
            current_zone = int(predicted_zone)
            acceptance = int(real_acceptance)
            wrinkles_with_zone.append(ZonePredictionProps(current_zone, acceptance))
        return wrinkles_with_zone

    @staticmethod
    def filter_out_bellow_threshold(unfiltered_wrinkless_list: List[ZonePredictionProps],
                                    acceptance_threshold: int = 1) -> List[ZonePredictionProps]:
        filtered_zones_wrinkless_list = []
        for record in unfiltered_wrinkless_list:
            if record.acceptance <= acceptance_threshold:
                filtered_zones_wrinkless_list.append(record)
        return filtered_zones_wrinkless_list

    def get_steaming_zones_sequence(self, predicted_wrinkles: Dict) -> List[ZonePredictionProps]:
        zones_sorted_time_steaming_cycle_list = []

        if len(predicted_wrinkles) == 0:
            logging.info('No wrinkles to evaluate steaming!')

        else:
            wrinkles_with_zone = self.get_wrinkles_with_zone_and_acceptance(predicted_wrinkles)
            # Step 1 - keep only predictions without green acceptance_threshold
            severe_wrinkles_list = self.filter_out_bellow_threshold(wrinkles_with_zone, self.acceptance_threshold)
            if len(severe_wrinkles_list) == 0:
                logging.info('No severe_wrinkles to iron, wrinkless above acceptance_threshold threshold !')
            else:
                # Step 2 - sort the list according to zone time mapping
                zones_sorted_time_steaming_cycle_list = self.sort_zones_according_to_zone_time_mapping(
                    severe_wrinkles_list)

        return zones_sorted_time_steaming_cycle_list

    def select_zones_according_to_time(self, zones: List[ZonePredictionProps],
                                       zone_time_mapping: Dict[ZoneDescriptorKey, ZoneDescriptorValue],
                                       transition_time: Dict, time_threshold: int, previous_transition_point: str,
                                       initial_cumulated_time: float):
        cumulated_time = initial_cumulated_time
        selected_zones = []
        steaming_sequence_record = []
        current_transition_time = 0
        current_zone_steaming_time = 0
        trajectory_occurence = 0

        for zone_input in zones:
            composed_key = ZoneDescriptorKey(self.plant_project, zone_input.zone, zone_input.acceptance,
                                             self.cover_material)

            current_zone_descriptor_values = zone_time_mapping[composed_key]
            new_transition_point = current_zone_descriptor_values.transition_point

            current_next_transition_key = TransitionDescriptor(previous_transition_point, new_transition_point)
            current_transition_time = transition_time[current_next_transition_key]

            current_zone_steaming_time = float(current_zone_descriptor_values.time)
            trajectory_occurence = int(current_zone_descriptor_values.trajectory_occurence)

            cumulated_time += current_zone_steaming_time * trajectory_occurence
            cumulated_time += current_transition_time

            if cumulated_time > time_threshold:
                break
            time_zone_record = {'input_zone': zone_input.zone, 'acceptance_threshold': zone_input.acceptance,
                                'transition points': previous_transition_point + ' ' + new_transition_point,
                                'transition_time': current_transition_time, 'steaming_time': current_zone_steaming_time}
            steaming_sequence_record.append(time_zone_record)
            selected_zones.append(zone_input)
            previous_transition_point = new_transition_point

        if len(zones) == 0:
            theoretical_working_time = 0
        elif cumulated_time > time_threshold:
            theoretical_working_time = cumulated_time - current_transition_time
            theoretical_working_time -= current_zone_steaming_time * trajectory_occurence
        else:
            theoretical_working_time = cumulated_time

        return selected_zones, steaming_sequence_record, round(theoretical_working_time, 1)

    def change_zones_to_abb_format(self, zones_meta: List[ZonePredictionProps],
                                   zone_time_mapping: Dict[ZoneDescriptorKey, ZoneDescriptorValue], program_number: str,
                                   serial_number: str) -> List[List]:
        abb_format = [[program_number, serial_number, None, None, None, None, None, None, None, None, None]]
        steaming_zone_order_number = 1
        for current_zone_meta in zones_meta:
            current_zone = int(current_zone_meta.zone)
            current_acceptance = int(current_zone_meta.acceptance)
            composed_key = ZoneDescriptorKey(self.plant_project, current_zone, current_acceptance,
                                             self.cover_material)

            if composed_key in zone_time_mapping.keys():
                zone_descriptor_value = zone_time_mapping[composed_key]

                input_offset_x: int = zone_descriptor_value.input_offset_x
                input_offset_y: int = zone_descriptor_value.input_offset_y
                input_offset_z: int = zone_descriptor_value.input_offset_z
                output_offset_x: int = zone_descriptor_value.output_offset_x
                output_offset_y: int = zone_descriptor_value.output_offset_y
                output_offset_z: int = zone_descriptor_value.output_offset_z
                steam: int = zone_descriptor_value.steam
                speed: int = zone_descriptor_value.speed
                pressure: int = zone_descriptor_value.pressure

                # abb_format.append(
                #     [str(steaming_zone_order_number), str(current_zone), speed, steam, pressure, input_offset_x,
                #      input_offset_y, input_offset_z, output_offset_x, output_offset_y, output_offset_z])
                abb_format.append(
                    [steaming_zone_order_number, current_zone, speed, steam, pressure, input_offset_x,
                     input_offset_y, input_offset_z, output_offset_x, output_offset_y, output_offset_z])
            else:
                logging.warning(f'{composed_key} does not exist in configuration file, default values used')
                abb_format.append(
                    [str(steaming_zone_order_number), str(current_zone)] + self.get_default_parameters())

            steaming_zone_order_number = steaming_zone_order_number + 1

        return abb_format

    def define_zones_to_steam_in_abb_format_according_to_available_time(self, predicted_wrinkles: Dict,
                                                                        zone_time_mapping: Dict[
                                                                            ZoneDescriptorKey, ZoneDescriptorValue],
                                                                        transition_time_table: Dict[
                                                                            TransitionDescriptor, float],
                                                                        cycle_time: int,
                                                                        previous_transition_point: str,
                                                                        cumulated_time: float,
                                                                        serial_number: str,
                                                                        program_number: str
                                                                        ):

        steaming_zones_sequence = self.get_steaming_zones_sequence(predicted_wrinkles)
        selected_zones, steaming_sequence_record, theoretical_working_time = self.select_zones_according_to_time(
            zones=steaming_zones_sequence, zone_time_mapping=zone_time_mapping, transition_time=transition_time_table,
            time_threshold=cycle_time, previous_transition_point=previous_transition_point,
            initial_cumulated_time=cumulated_time
        )

        zone_to_steam_in_abb_format = self.change_zones_to_abb_format(selected_zones, zone_time_mapping, program_number,
                                                                      serial_number)

        return zone_to_steam_in_abb_format, steaming_sequence_record, theoretical_working_time
