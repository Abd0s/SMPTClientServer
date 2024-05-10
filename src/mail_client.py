import socket
import traceback
import argparse
import sys


class ProgramArgs(argparse.Namespace):
    ip_address: str
    port: int


class BaseClient:
    def __init__(self, debug: bool = False) -> None:
        self.recieve_buffer: bytes = bytes()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.debug: bool = debug

    def read_until(self, sequence: bytes) -> str | None:
        # Read data into buffer as it is available
        # Check if buffer contains `character`
        # Trim buffer until `character` and return the data
        while sequence not in self.recieve_buffer:
            data = self.server_socket.recv(1024)
            if not data:  # socket closed
                return None
            self.recieve_buffer += data
        until_data, sep, self.recieve_buffer = self.recieve_buffer.partition(sequence)
        if self.debug:
            print(f"DEBUG | READ DATA: {until_data.decode()}")
        return until_data.decode()


class SmptClient(BaseClient):
    def __init__(self, ip_address: str, port: int) -> None:
        super().__init__(debug=True)
        try:
            self.server_socket.connect((ip_address, port))
        except TimeoutError:
            print("Socket timeout while connecting")
            sys.exit()
        except Exception:
            print("An error occured while connecting to SMTP server")
            traceback.print_exc()
            sys.exit()

        self.server_addr = ip_address
        self.addr: str = self.server_socket.getsockname()[0]
        self._emptystring: str = ""
        self._linesep: str = "\r\n"
        self._dotsep: str = "."
        self._newline: str = "\n"
        self.terminator: bytes = b"\r\n"

        # 220 Service ready response on connection with the server
        self._handle_response("220", self.read_until(self.terminator))

        self.smtp_HELO()
        
        print("Smpt server set up succesfully")

    def send_command(self, command: str) -> None:
        self.server_socket.sendall(bytes(command + "\r\n", encoding="utf-8"))

    def send_data(self, data: str) -> None:
        # Add extraneous carriage returns and transparency according
        # to RFC 5321, Section 4.5.2.
        mail_data = []
        for line in data.split(self._newline):
            if line and line[0] == self._dotsep:
                mail_data.append(self._dotsep + line)
            else:
                mail_data.append(line)
        mail_str = (
            self._linesep.join(mail_data) + self._linesep + self._dotsep + self._linesep
        )
        self.server_socket.sendall(bytes(mail_str, encoding="utf-8"))

    def close(self) -> None:
        self.smtp_QUIT()
        self.server_socket.close()
        
    def send_mail(self, sender: str, receiver: str, subject: str, message: str) -> None:
        self.smtp_MAIL(sender)
        self.smtp_RCPT(receiver)
        email_header: str = f"From: {sender}\n" + f"To: {receiver}\n" + f"Subject: {subject}\n"
        self.smtp_DATA(email_header + message)
        
    def _handle_response(self, expected_code: str, response: str | None) -> None:
        if response is None:
            raise RuntimeError("Unexpected socket closure")
        elif not response.startswith(expected_code):
            raise RuntimeError(f"Unexpected response: {response}")

    # PROTOCOL IMPLEMENTATION
    def smtp_HELO(self) -> None:
        self.send_command(f"HELO {self.addr}")
        self._handle_response("250", self.read_until(self.terminator))

    def smtp_RCPT(self, receiver: str) -> None:
        self.send_command(f"RCPT TO: <{receiver}>")
        self._handle_response("250", self.read_until(self.terminator))

    def smtp_MAIL(self, sender: str) -> None:
        self.send_command(f"MAIL FROM: <{sender}>")
        self._handle_response("250", self.read_until(self.terminator))

    def smtp_DATA(self, data: str) -> None:
        self.send_command("DATA")
        self._handle_response("354", self.read_until(self.terminator))
        self.send_data(data)
        self._handle_response("250", self.read_until(self.terminator))

    def smtp_QUIT(self) -> None:
        self.send_command("QUIT")
        self._handle_response("221", self.read_until(self.terminator))


class PopClient(BaseClient):
    def __init__(self, ip_address: str, port: int) -> None:
        super().__init__(debug=True)

        try:
            self.server_socket.connect((ip_address, port))
        except TimeoutError:
            print("Socket timeout while connecting")
            sys.exit()
        except Exception:
            print("An error occured while connecting to POP3 server")
            traceback.print_exc()
            sys.exit()

        self.server_addr = ip_address
        self.addr: str = self.server_socket.getsockname()[0]
        self._emptystring: str = ""
        self._linesep: str = "\r\n"
        self._dotsep: str = "."
        self._newline: str = "\n"
        self.terminator: bytes = b"\r\n"

    
def mail_sending_cli(args: ProgramArgs) -> None:
    # Collect mail information
    # TODO ADD FORMAT VALIDATION FOR ADDRESSES
    sender: str = input("From: ")
    receiver: str = input("To: ")
    subject: str = input("Subject: ")

    print("Mail content:")
    message: list[str] = []
    while True:
        line = input()
        if line == ".":  # end of message indicator
            break
        else:
            message.append(line)

    message_str: str = "\n".join(message)

    if len(subject) > 150:
        print("Incorrect mail format: Subject can't be longer than 150 characters")
        return

    # Create SMPT client
    try:
        smpt_client = SmptClient(args.ip_address, args.port)
    except Exception:
        print("Error creating smpt client")
        traceback.print_exc()
        return

    try:
        smpt_client.send_mail(sender, receiver, subject, message_str)
    except Exception:
        print("Error sending mail")
        traceback.print_exc()
        return

    smpt_client.close()


def mail_management_cli() -> None:
    user_name = input("Enter username: ")
    password = input("Enter password: ")


def mail_searching_cli() -> None:
    pass


def user_interaction(args) -> None:
    # Ask for authentication information

    while True:
        # Option menu
        print("- Mail client - Please choose an option from the menu:")
        print("")
        print("[a] Mail sending:")
        print("[b] Mail management")
        print("[c] Mail searching")
        print("[d] Exit")

        while True:
            menu_option = input("Enter an menu option: ")
            if menu_option in ["a", "A", "b", "B", "c", "C", "d", "D"]:
                break
            else:
                print("Invalid menu option, please choose when of the menu options.")

        match menu_option:
            case "a" | "A":
                mail_sending_cli(args)
            case "b" | "B":
                print("Mail management")
            case "c" | "C":
                print("Mail searching")
            case "d" | "D":
                sys.exit(0)


if __name__ == "__main__":
    # Command line arguments
    parser = argparse.ArgumentParser(
        prog="Mail client", description="A basic mail client using SMTP and POP3."
    )
    parser.add_argument(
        "ip_address",
        metavar="IP",
        type=str,
        help="IP address of the mail server machine.",
    )
    parser.add_argument(
        "port", metavar="P", type=int, help="Port to connect mail server on."
    )

    args: ProgramArgs = parser.parse_args()  # type: ignore

    user_interaction(args)
