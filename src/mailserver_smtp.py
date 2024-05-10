import sys
import socket
import threading
import logging
import argparse
import errno

import misc_utils

logger = logging.getLogger(__name__)


class ProgramArgs(argparse.Namespace):
    port: int

class SmtpServer:
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

        logger.info("SMTP server: waiting to connect to clients")
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
    COMMAND = 0
    DATA = 1

    def __init__(
        self, connection_socket: socket.socket, host: str
    ) -> None:
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

        self._set_post_data_state()
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
        self.send_response(f"220 {self.addr} Service Ready")

    def run(self):
        # STRATEGY:
        # IN A LOOP:
        # READ UNTIL DELIMITER
        # USE STRIP COMMAND KEYWORD TO DETERMINE COMMAND AND CALL APPRIOPRIATE COMMAND HANDLER

        try:
            while (data := self._read_until(self.terminator)) is not None:
                logger.debug(f"Data: {data}")
                if self.smtp_state == self.COMMAND:
                    # Handle case where data is an empty string
                    if not data:
                        self.send_response("500 Error: bad syntax")
                        continue
                    # Find command keyword
                    i = data.find(" ")
                    # Handle case where there is only a command keyword
                    if i < 0:
                        command = data.upper()
                        arg = None
                    # Handle case where there is a command keyword and additional arguments
                    else:
                        command = data[:i].upper()
                        arg = data[i + 1 :].strip()
                    # Find and call method to handle command
                    method = getattr(self, "smtp_" + command, None)
                    if not method:
                        self.send_response(
                            f'500 Error: command "{command}" not recognized'
                        )
                        continue
                    method(arg)
                elif self.smtp_state == self.DATA:
                    # Remove extraneous carriage returns and de-transparency according
                    # to RFC 5321, Section 4.5.2.
                    mail_data = []
                    for line in data.split(self._linesep):
                        if line and line[0] == self._dotsep:
                            mail_data.append(line[1:])
                        else:
                            mail_data.append(line)
                    received_data = self._newline.join(mail_data)
                    status = self.process_mail(
                        self.peer, self.mailfrom, self.rcpttos, received_data
                    )
                    self._set_post_data_state()
                    if not status:
                        self.send_response("250 OK")
                    else:
                        self.send_response(status)
                else:
                    self.send_response("451 Internal confusion")
        except Exception as e:
            logger.error(
                f"En error occured in the connection handle for peer {self.peer}",
                exc_info=e,
            )
            self.conn.close()
            
    def process_mail(self, peer, mailfrom, rcpttos, data) -> str | None:
        pass
    
    def close(self) -> None:
        logger.debug("Socket has been closed")
        self.conn.close()
        logger.debug("Ending connection thread")
        sys.exit()

    def send_response(self, msg: str) -> None:
        self.conn.sendall(bytes(msg + "\r\n", encoding="utf-8"))

    def _set_post_data_state(self):
        """Reset state variables to their post-DATA state."""
        self.smtp_state = self.COMMAND
        self.mailfrom = None
        self.rcpttos = []
        self.terminator = b"\r\n"

    def _read_until(self, sequence: bytes) -> str | None:
        # Read data into buffer as it is available
        # Check if buffer contains `character`
        # Trim buffer until `character` and return the data
        while sequence not in self.recieve_buffer:
            data = self.conn.recv(1024)
            if not data:  # socket closed
                return None
            self.recieve_buffer += data
        until_data, sep, self.recieve_buffer = self.recieve_buffer.partition(sequence)
        if self.debug:
            logger.debug(f"DATA: {until_data.decode()}")
        return until_data.decode()

    def _strip_command_keyword(self, keyword: str, data: str) -> str:
        keylen = len(keyword)
        if data[:keylen].upper() == keyword:
            return data[keylen:].strip()
        return ""

    def _getaddr(self, data: str) -> tuple[str, str]:
        """
        Extracts address information from the given data string.

        Args:
            data: The data string containing address information.

        Returns:
            tuple: A tuple containing the extracted address and the remaining portion of the data.
        """
        start_index = data.find("<")
        end_index = data.find(">")
        if start_index != -1 and end_index != -1:
            address = data[start_index + 1 : end_index]
            remainder = data[end_index + 1 :]
            return address, remainder
        else:
            return "", data

    # PROTOCOL IMPLEMANTATION
    def smtp_HELO(self, data: str) -> None:
        # Handle case where no hostname has been send
        if not data:
            self.send_response("501 Syntax: HELO hostname")
            return
        # Handle case where HELO command has been send prior
        if self.seen_greeting:
            self.send_response("503 Duplicate HELO")
            return
        self._set_post_data_state()
        self.seen_greeting = data
        self.send_response(f"250 OK Hello {self.fqdn}")

    def smtp_MAIL(self, data: str) -> None:
        # Handle case where no prior HELO command has been send
        if not self.seen_greeting:
            self.send_response("503 Error: send HELO first")
            return
        logger.debug(f"===> MAIL {data}")
        syntaxerr = "501 Syntax: MAIL FROM: <address>"
        # Handle command format syntax errors
        if data is None:
            self.send_response(syntaxerr)
            return
        data = self._strip_command_keyword("FROM:", data)
        address, params = self._getaddr(data)
        if not address:
            self.send_response(syntaxerr)
            return
        # Handle case where prior MAIL command has been sent
        if self.mailfrom:
            self.send_response("503 Error: nested MAIL command")
            return
        # Handle case where there are potentialy parameters (not supported)
        if params:
            self.send_response(
                "555 MAIL FROM parameters not recognized or not implemented"
            )
            return
        self.mailfrom = address
        self.send_response(f"250 {self.mailfrom} Sender OK")

    def smtp_RCPT(self, data: str) -> None:
        # Handle case where no HELO command has been send prior
        if not self.seen_greeting:
            self.send_response("503 Error: send HELO first")
            return
        logger.debug(f"===> RCPT {data}")
        # Handle case where no prior MAIL command has been send
        if not self.mailfrom:
            self.send_response("503 Error: need MAIL command")
            return
        syntaxerr = "501 Syntax: RCPT TO: <address>"
        # Handle command format syntax errors
        if data is None:
            self.send_response(syntaxerr)
            return
        data = self._strip_command_keyword("TO:", data)
        address, params = self._getaddr(data)
        if not address:
            self.send_response(syntaxerr)
            return
        # Handle case where there are potentialy parameters (not supported)
        if params:
            self.send_response(
                "555 RCPT TO parameters not recognized or not implemented"
            )
            return
        self.rcpttos.append(address)
        self.send_response("250 Recipient Ok")

    def smtp_DATA(self, data: str) -> None:
        # Handle case where no HELO command has been send prior
        if not self.seen_greeting:
            self.send_response("503 Error: send HELO first")
            return
        # Handle case where no RCPT command has been send prior
        if not self.rcpttos:
            self.send_response("503 Error: need RCPT command")
            return
        # Handle command format syntax error
        if data:
            self.send_response("501 Syntax: DATA")
            return
        self.smtp_state = self.DATA
        self.terminator = b"\r\n.\r\n"
        self.send_response("354 End data with <CR><LF>.<CR><LF>")

    def smtp_QUIT(self, data: None) -> None:
        self.send_response(f"221 {self.addr} Closing connection")
        self.close()

    # TODO FIX OR REMOVE AS POTENTIALLY MAKES NO SENSE ATM
    def smtp_VRFY(self, data: str) -> None:
        if data:
            address, params = self._getaddr(data)
            if address:
                self.send_response(
                    "252 Cannot VRFY user, but will accept message "
                    "and attempt delivery"
                )
            else:
                self.send_response("502 Could not VRFY %s" % data)
        else:
            self.send_response("501 Syntax: VRFY <address>")

    def smtp_RSET(self, data: str) -> None:
        if data:
            self.send_response("501 Syntax: RSET")
            return
        self._set_post_data_state()
        self.send_response("250 OK")

    def smtp_NOOP(self, data: str) -> None:
        if data:
            self.send_response("501 Syntax: NOOP")
        else:
            self.send_response("250 OK")

    def smtp_HELP(self, data: str):
        if data:
            lc_arg = data.upper()
            if lc_arg == "HELO":
                self.send_response("250 Syntax: HELO hostname")
            elif lc_arg == "MAIL":
                msg = "250 Syntax: MAIL FROM: <address>"
                self.send_response(msg)
            elif lc_arg == "RCPT":
                msg = "250 Syntax: RCPT TO: <address>"
                self.send_response(msg)
            elif lc_arg == "DATA":
                self.send_response("250 Syntax: DATA")
            elif lc_arg == "RSET":
                self.send_response("250 Syntax: RSET")
            elif lc_arg == "NOOP":
                self.send_response("250 Syntax: NOOP")
            elif lc_arg == "QUIT":
                self.send_response("250 Syntax: QUIT")
            elif lc_arg == "VRFY":
                self.send_response("250 Syntax: VRFY <address>")
            else:
                self.send_response(
                    "501 Supported commands: HELO MAIL RCPT " "DATA RSET NOOP QUIT VRFY"
                )
        else:
            self.send_response(
                "250 Supported commands: HELO MAIL RCPT DATA " "RSET NOOP QUIT VRFY"
            )


if __name__ == "__main__":
    # Command line arguments
    parser = argparse.ArgumentParser(
        prog="SMTP server", description="A basic SMPT server."
    )
    parser.add_argument(
        "port", metavar="P", type=int, help="Port to open the server on."
    )

    args: ProgramArgs = parser.parse_args()  # type: ignore

    # Set up logging to stdo
    misc_utils.setup_logger()

    # Create and start server
    server = SmtpServer("localhost", args.port)
    server.start()
