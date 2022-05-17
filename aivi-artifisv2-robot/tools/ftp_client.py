import csv
import os
import tempfile
from ftplib import FTP, all_errors
from typing import List


class FtpClient:
    def __init__(self, input_logger, orders_file_name, output_directory, ip_server: str, port: int = 21, user: str = "",
                 password: str = ""):
        self.logger = input_logger
        self.user = user
        self.password = password
        self.ip_server = ip_server
        self.port = port
        self.ftp_client = FTP()
        self.directories = []
        self.files = []
        self.orders_file_name = orders_file_name
        self.output_directory = output_directory
        
    def get_connection(self) -> None:
        self.ftp_client.connect(self.ip_server, self.port)
        self.ftp_client.login(self.user, self.password)
        self.ftp_client.set_pasv(True)

    def get_disconnection(self) -> None:
        self.ftp_client.close()

    def write_and_push_temporary_file_to_robot(self, zones: List) -> str:
        self.logger.info('write and push orders.csv file to ftp server')
        status = 'OK'
        try:
            self.get_connection()
            self.logger.info('connection with FTP server done')

            files_in_ftp = []
            self.ftp_client.retrlines('LIST', lambda line: files_in_ftp.append(line.split()[-1]))

            f = tempfile.NamedTemporaryFile(mode='w', newline='', delete=False)
            writer = csv.writer(f)
            writer.writerows(zones)
            f.close()
            self.ftp_client.storlines(f'STOR {self.output_directory}/{self.orders_file_name}', open(f.name, 'rb'))
            
            os.remove(f.name)

        except all_errors as e:
            self.logger.error(f'Error when uploading file on ABB FTP - {e}')
            self.get_disconnection()
            status = 'FTP error'

        return status
