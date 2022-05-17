import csv
import json
import logging
from enum import Enum
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, Any, Union


class ConfigurationExtension(Enum):
    JSON = '.json'
    CSV = '.csv'


class InvalidConfigurationFile(Exception):
    pass


def load_data_from_json_file(file_path: Union[str, Path], logger: logging.getLogger()) -> Dict[str, Any]:
    if isinstance(file_path, str):
        file_path = Path(file_path)

    if not file_path.is_file():
        log_message = f'File {file_path.absolute()} not found'
        logger.error(log_message)
        raise FileNotFoundError(log_message)

    try:
        with open(file_path) as file_content:
            return json.load(file_content)
    except JSONDecodeError:
        log_message = f'The file {file_path.absolute()} is not a valid json file'
        logger.error(log_message)
        raise InvalidConfigurationFile(log_message)


def read_resource_csv(file_path: Union[str, Path], reader_class=csv.DictReader):
    if isinstance(file_path, str):
        file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(f'File {file_path.absolute()} not found')
    with file_path.open() as stream:
        reader = reader_class(stream, skipinitialspace=True)
        for row in reader:
            yield {key.strip(): value.strip() for key, value in row.items()}


def convert_csv_to_dict(file_path, key_column, logger: logging.getLogger()):
    """
    Convert a CSV file to a dict using values of a specific column as the dict keys

    :param logger: to log messages
    :param file_path: str or Path: location of the csv file
    :param key_column: str: Column which values will be the keys of the dict
    :return: dict
    """
    logger.info('Converting the csv file %s using the key column %s', str(file_path), key_column)
    result = {}
    for row in read_resource_csv(file_path):
        try:
            key = row[key_column]
        except KeyError:
            logger.error('Key column %s does not exists in csv file %s', key_column, str(file_path))
            raise
        if key in result:
            logger.warning('Key %s already in sheet', key)
            logger.warning('Old row: %s / New row: %s', result[key], row)
        result[key] = row
    logger.info('Done converting of csv file')
    return result


def save_dict_in_json(input_dict, out_put_path):
    with open(out_put_path, 'w') as file:
        json.dump(input_dict, file, indent=4, separators=(",", ":"))


def write_list_to_csv_file(logger: logging.getLogger(), list_to_copy, file_path):
    try:
        with open(file_path, 'w', newline='') as used_file:
            writer = csv.writer(used_file, quoting=csv.QUOTE_NONE)
            writer.writerows(list_to_copy)
            return 'OK'
    except Exception as e:
        logger.error(f'{e} exception was produced...')
        return 'NOK'
