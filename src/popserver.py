import errno
import socket
import threading
import logging
import argparse
import sys
import pathlib

import filelock

import misc_utils
import mailbox_manager

logger = logging.getLogger(__name__)

USERSFILE = pathlib.Path(__file__).parent.parent.resolve() / "users"

class ProgramArgs(argparse.Namespace):
    port: int


class Pop3Server:
    def __init__(self, ip_address: str, port: int) -> None:
        self.ip_address = ip_address
        self.port = port

    def start(self) -> None:
        self.accept_new_connections()

    def accept_new_connections(self) -> None:
        new_connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_connection_socket.settimeout(1)

        new_connection_socket.bind((self.ip_address, self.port))
        new_connection_socket.listen()

        logger.info("POP3 server: waiting to connect to clients")
        while True:
            try:
                sock, addr = new_connection_socket.accept()
            except socket.timeout:
                # Allows to kill using CTLR+C
                continue
            except IOError as e:
                logger.error("An error occured:", exc_info=e)

            logger.info(f"Connected to client with {addr=}")
            connection_thread = ConnectionHandle(sock, self.ip_address)
            connection_thread.start()

        new_connection_socket.close()


class ConnectionHandle(threading.Thread):
    # POP3 STATES
    AUTH = 0
    TRANSACTION = 1

    # AUTH STATES
    NO_STATE = 0
    USER = 1

    def __init__(self, connection_socket: socket.socket, host: str) -> None:
        super().__init__(daemon=True)

        self.debug: bool = False

        self.recieve_buffer: bytes = bytes()
        self.conn = connection_socket
        self.addr = host
        self._emptystring: str = ""
        self._linesep: str = "\r\n"
        self._dotsep: str = "."
        self._newline: str = "\n"
        self.terminator: bytes = b"\r\n"

        self._reset_state()
        self.seen_greeting: str = ""
        self.fqdn = socket.getfqdn()

        try:
            self.peer = self.conn.getpeername()
        except OSError as e:
            # a race condition  may occur if the other end is closing
            # before we can get the peername
            self.conn.close()
            if e.errno != errno.ENOTCONN:
                raise
            return

        logger.debug(f"Peer: {self.peer}")
        self.send_postive_response("POP3 server ready")

    def run(self):
        
    
    def _reset_state(self) -> None:
        self.pop3_state: int = self.AUTH
        self.auth_state: int = self.NO_STATE
    
    def send_postive_response(self, msg: str) -> None:
        self.conn.sendall(bytes(f"+OK {msg}\r\n", encoding="utf-8"))

    def send_negative_response(self, msg: str) -> None:
        self.conn.sendall(bytes(f"-ERR {msg}\r\n", encoding="utf-8"))

    def send_response(self, msg: str) -> None:
        self.conn.sendall(bytes(msg + "\r\n", encoding="utf-8"))

    def read_until(self, sequence: bytes) -> str | None:
        # Read data into buffer as it is available
        # Check if buffer contains `character`
        # Trim buffer until `character` and return the data
        while sequence not in self.recieve_buffer:
            data = self.conn.recv(1024)
            if not data:  # socket closed
                return None
            self.recieve_buffer += data
        until_data, sep, self.recieve_buffer = self.recieve_buffer.partition(sequence)
        return until_data.decode()

    def _load_maildrop(self, username: str) -> None:
        if self.mailbox_lock.is_locked:
            self.maildrop = mailbox_manager.get_all_mails(USERSFILE, username)
        else:
            logger.error("Tried to aquire maildrop without holding the lock")
            
    def close(self) -> None:
        logger.debug("Socket has been closed")
        self.conn.close()
        logger.debug("Ending connection thread")
        sys.exit()
        
    # PROTOCOL IMPLEMANTATION
    def pop3_QUIT(self, args: str) -> None:
        if self.pop3_state == self.AUTH:
            self.send_postive_response("POP3 server signing off")
            self.close()
        if self.pop3_state == self.TRANSACTION:
            

    # AUTH STATE ONLY COMMANDS
    def pop3_USER(self, args: list[str]) -> None:
        if self.auth_state == self.NO_STATE:
            try:
                if args[0] in mailbox_manager.get_users(USERSFILE):
                    self.send_postive_response(f"{args[0]} is a valid mailbox")
                    self.auth_state = self.USER
                    self.username = args[0]
                else:
                    self.send_negative_response("No mailbox for given user")
            except IndexError:
                self.send_negative_response("Invalid argument")
        elif self.auth_state == self.USER:
            self.send_negative_response("Invalid command sequence, USER command already received succesfully")
            
    def pop3_PASS(self, args: list[str]) -> None:
        if self.auth_state == self.USER:
            try:
                if mailbox_manager.validate_user(USERSFILE, self.username, args[0]):
                    self.mailbox_lock = mailbox_manager.get_lock(self.username, USERSFILE)
                    try:
                        self.mailbox_lock.acquire(blocking=False)
                        self.send_postive_response("Maildrop locked and ready")
                        self._load_maildrop(self.username)
                        self.pop3_state = self.TRANSACTION
                    except filelock.Timeout:
                        self.send_negative_response("Unable to lock maildrop")
                else:
                    self.send_negative_response("Invalid password")
            except IndexError:
                self.send_negative_response("Invalid argument")
        else:
            self.send_negative_response("Invalid command sequence, must send USER command first")
            self.auth_state = self.NO_STATE

    def pop3_APOP(self, args: list[str]) -> None:
        self.send_negative_response("Unimplemented command")
            
    # TRANSACTION STATE ONLY COMMANDS
    def pop3_STAT(self, args: list[str]) -> None:
        if self.pop3_state == self.TRANSACTION:
            self.send_postive_response(f"{len([mail for mail in self.maildrop if mail])} {sum([len(mail.encode("utf-8")) for mail in self.maildrop if mail])}")
        else:
            self.send_negative_response("Not in transaction state, use USER/PASS first to authenticate")

    def pop3_LIST(self, args: list[str]) -> None:
        if self.pop3_state == self.TRANSACTION:
            if not args:
                try:
                    self.send_postive_response(f"{args[0]} {len(self.maildrop[int(args[0]) + 1].encode("utf-8"))}")
                except IndexError:
                    self.send_negative_response(f"No such mail, only {len(self.maildrop)} mails in maildro")
                except ValueError:
                    self.send_negative_response("Invalid argument, must be an integer")
            else:
                self.send_postive_response(f"{len(self.maildrop)} mails")
                for index, mail in enumerate(self.maildrop, 1):
                    self.send_response(f"{index} {len(mail.encode("utf-8"))}")
                self.send_response(".\r\n")
        else:
            self.send_negative_response("Not in transaction state, use USER/PASS first to authenticate")
            
    def pop3_RETR(self, args: list[str]) -> None:
        if self.pop3_state == self.TRANSACTION:
            if args:
                try:
                    if self.maildrop[int(args[0]) - 1)]:
                        self.send_postive_response(f"{len(self.maildrop[int(args[0]) - 1].encode("utf-8"))}")
                        self.send_response()
                    
                except IndexError:
                    self.send_negative_response("Invalid mail number, nu such mail")

            else:
                self.send_negative_response("Invalid argument, requires a valid mail number")

        else:
            self.send_negative_response("Not in transaction state, use USER/PASS first to authenticate")
            
            
    # TODO FIX NEGARTIVE INDEXES
    def pop3_DELE(self, args: list[str]) -> None:
        if self.pop3_state == self.TRANSACTION:
            if args:
                try:
                    if self.maildrop[int(args[0]) - 1]:
                        self.maildrop[int(args[0]) - 1] = ""
                        self.send_postive_response("Message {args[0]} deleted")
                    else:
                        self.send_negative_response(f"Message {args[0]} already deleted")
                except IndexError:
                    self.send_negative_response("Invalid mail number, no such mail")
            else:
                self.send_negative_response("Invalid argument, requires a valid mail number")
        else:
            self.send_negative_response("Not in transaction state, use USER/PASS first to authenticate")
            

    def pop3_NOOP(self, args: list[str]) -> None:
        if self.pop3_state == self.TRANSACTION:
            self.send_postive_response("NOOP response")
        else:
            self.send_negative_response("Not in transaction state, use USER/PASS first to authenticate")
            

    def pop3_RSET(self, args: list[str]) -> None:
        if self.pop3_state == self.TRANSACTION:
            self._load_maildrop(self.username)
            self.send_postive_response(f"maildrop has {len(self.maildrop)} mails")
        else:
            self.send_negative_response("Not in transaction state, use USER/PASS first to authenticate")
            

    # OPTIONAL COMMANDS
    def pop3_TOP(self, args: list[str]) -> None:
        if self.pop3_state == self.TRANSACTION:
            self.send_negative_response("Unimplemented command")
        else:
            self.send_negative_response("Not in transaction state, use USER/PASS first to authenticate")
            

    def pop3_UIDL(self, args: str) -> None:
        if self.pop3_state == self.TRANSACTION:
            self.send_negative_response("Unimplemented command")
        else:
            self.send_negative_response("Not in transaction state, use USER/PASS first to authenticate")
           

if __name__ == "__main__":
    # Command line arguments
    parser = argparse.ArgumentParser(
        prog="POP3 server", description="A basic POP3 server."
    )
    parser.add_argument(
        "port", metavar="P", type=int, help="Port to open the server on."
    )

    args: ProgramArgs = parser.parse_args()  # type: ignore

    # Set up logging to stdo
    misc_utils.setup_logger()

    # Create and start server
    server = Pop3Server("localhost", args.port)
    server.start()
