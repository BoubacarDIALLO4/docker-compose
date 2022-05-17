import time
from pathlib import Path
from threading import Thread
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

TEST_DIR = Path(__file__).absolute().parent.parent

FTP_FOLDER = (TEST_DIR / 'test_folder/artifis_ftp_folder').resolve().as_posix()


class FtpTestServer(Thread):
    def __init__(self, port: int, ftp_folder: Path):
        super().__init__()
        self.authorizer = DummyAuthorizer()
        self.authorizer.add_user('user', 'password', ftp_folder, perm='elradfmwMT')
        self.authorizer.add_anonymous(ftp_folder)
        self.handler = FTPHandler
        self.handler.authorizer = self.authorizer

        # Adding Passive Port Range
        self.handler.passive_ports = range(1000, 8500)

        self.server = FTPServer(("127.0.0.1", port), self.handler)


    def run(self):
        self.server.serve_forever(timeout=10)

    def stop(self):
        self.server.close_all()


def main():
    try:
        print('start local FTP server')

        ftp_server = FtpTestServer(2121, FTP_FOLDER)
        ftp_server.start()

        while True:
            time.sleep(.3)

    except KeyboardInterrupt:
        print('Quit')
        ftp_server.stop()


if __name__ == "__main__":
    main()
