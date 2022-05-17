import logging
from collections import namedtuple
from itertools import islice
from pathlib import Path
from typing import Dict, List
from tools.file import read_resource_csv

TRANSITION_POINT_INDEX = 7
START_POSITION_INDEX = 0
ARRIVAL_POSITION_INDEX = 1

ZoneDescriptorKey = namedtuple('ZoneDescriptorKey', ['plant_project', 'zone_number', 'acceptance', 'cover_material'])
ZoneDescriptorValue = namedtuple('ZoneDescriptorValue', ['time',
                                                         'input_offset_x',
                                                         'input_offset_y',
                                                         'input_offset_z',
                                                         'output_offset_x',
                                                         'output_offset_y',
                                                         'output_offset_z',
                                                         'transition_point',
                                                         'steam',
                                                         'speed',
                                                         'trajectory_occurence',
                                                         'pressure'])

SeatTypeMaterialKey = namedtuple('SeatTypeMaterialKey', ['plant_project', 'cover_material'])
PriorityValue = namedtuple('PriorityValue', ['program_number', 'bypass_wrinkliness_8_9', 'priority'])

TransitionDescriptor = namedtuple('StreamerPositionTransition', ['from_position', 'to_position'])


def check_transition_points_zone_time_mapping_and_transition_time(
        zone_time_mapping: Dict[ZoneDescriptorKey, ZoneDescriptorValue],
        transition_time: Dict[TransitionDescriptor, float]) -> bool:
    check = False
    transition_points_from_zone_time_mapping = []

    for key, value in zone_time_mapping.items():
        transition_points_from_zone_time_mapping.append(value[TRANSITION_POINT_INDEX])

    lines_of_transition_points_from_transition_time = []
    columns_of_transition_points_from_transition_time = []

    for key, value in transition_time.items():
        lines_of_transition_points_from_transition_time.append(key[START_POSITION_INDEX])
        columns_of_transition_points_from_transition_time.append(key[ARRIVAL_POSITION_INDEX])

    set_from_lines_of_transition_points = set(lines_of_transition_points_from_transition_time)
    set_from_zone_transition_points = set(transition_points_from_zone_time_mapping)
    diff_sets_lines_and_zone = set_from_zone_transition_points.difference(set_from_lines_of_transition_points)
    diff_lines = len(diff_sets_lines_and_zone)

    set_from_columns_of_transition_points = set(columns_of_transition_points_from_transition_time)
    diff_sets_columns_and_zone = set_from_zone_transition_points.difference(set_from_columns_of_transition_points)
    diff_columns = len(diff_sets_columns_and_zone)

    if diff_lines == 0 and diff_columns == 0:
        check = True

    return bool(check)


def get_zone_time_mapping_and_zones_per_seat_type(time_zone_mapping_file_path: Path) -> tuple:
    zone_time_mapping: Dict[ZoneDescriptorKey, ZoneDescriptorValue] = {}
    zones_per_seat_type: Dict[str, List] = {}

    time_zone_mapping_file_content = read_resource_csv(time_zone_mapping_file_path)

    for row in time_zone_mapping_file_content:
        key = ZoneDescriptorKey(row['plant_project'],
                                int(row['zone_number']),
                                int(row['acceptance']),
                                row['cover_material'])
        if key in zone_time_mapping:
            logging.warning(f'Key "{key}" already in sheet')
        else:
            zone_time_mapping[key] = ZoneDescriptorValue(row['time'],
                                                         row['input_offset_x'],
                                                         row['input_offset_y'],
                                                         row['input_offset_z'],
                                                         row['output_offset_x'],
                                                         row['output_offset_y'],
                                                         row['output_offset_z'],
                                                         row['transition_point'],
                                                         row['steam'],
                                                         row['speed'],
                                                         row['trajectory_occurence'],
                                                         row['pressure'])

        key_seat_type = row['plant_project']
        value_zone_number = row['zone_number']
        if key_seat_type not in zones_per_seat_type:
            zones_per_seat_type[key_seat_type] = [value_zone_number]
        else:
            zones_per_seat_type[key_seat_type].append(value_zone_number)

    return zone_time_mapping, zones_per_seat_type


def get_transition_time(transition_time_table: Path) -> Dict[TransitionDescriptor, float]:
    transition_time: Dict[TransitionDescriptor, float] = {}

    transition_time_table_content = read_resource_csv(transition_time_table)
    for row in transition_time_table_content:
        current_position_key = list(row.keys())[0]
        current_transition_point = row[current_position_key]
        for transition, time in islice(row.items(), 1, None):
            current_destination_transition_key = TransitionDescriptor(current_transition_point, transition)

            try:
                transition_time[current_destination_transition_key] = float(time)

            except ValueError:
                logging.error(f'Value "{time}" is not a valid transition time value')

    return transition_time
