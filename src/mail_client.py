import socket
import traceback
import argparse
import sys
from typing import NamedTuple

class Mail(NamedTuple):
    sender: str
    receiver: str
    subject: str
    received_date: str
    body: str
    
def parse_mail(mail_data: str) -> Mail:
    lines = mail_data.splitlines()
    sender = lines[0].split()[1]
    receiver = lines[1].split()[1]
    subject = lines[2].split()[1]
    received_data = lines[3].split()[1]    
    body = "\n".join(lines[4:])
    return Mail(sender, receiver, subject, received_data, body)

class ProgramArgs(argparse.Namespace):
    ip_address: str
    pop3_port: int
    smtp_port: int


class BaseClient:
    def __init__(self, debug: bool = False) -> None:
        self.recieve_buffer: bytes = bytes()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.debug: bool = debug

    def _read_until(self, sequence: bytes) -> str | None:
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

    def send_command(self, command: str) -> None:
        self.server_socket.sendall(bytes(command + "\r\n", encoding="utf-8"))


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
        self._handle_response("220")

        self.smtp_HELO()

        print("Smpt client set up succesfully")

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
        email_header: str = (
            f"From: {sender}\n" + f"To: {receiver}\n" + f"Subject: {subject}\n"
        )
        self.smtp_DATA(email_header + message)

    def _handle_response(self, expected_code: str) -> None:
        response = self._read_until(self.terminator)
        if response is None:
            raise RuntimeError("Unexpected socket closure")
        elif not response.startswith(expected_code):
            raise RuntimeError(f"Unexpected response: {response}")

    # PROTOCOL IMPLEMENTATION
    def smtp_HELO(self) -> None:
        self.send_command(f"HELO {self.addr}")
        self._handle_response("250")

    def smtp_RCPT(self, receiver: str) -> None:
        self.send_command(f"RCPT TO: <{receiver}>")
        self._handle_response("250")

    def smtp_MAIL(self, sender: str) -> None:
        self.send_command(f"MAIL FROM: <{sender}>")
        self._handle_response("250")

    def smtp_DATA(self, data: str) -> None:
        self.send_command("DATA")
        self._handle_response("354")
        self.send_data(data)
        self._handle_response("250")

    def smtp_QUIT(self) -> None:
        self.send_command("QUIT")
        self._handle_response("221")


class Pop3Client(BaseClient):
    def __init__(self, ip_address: str, port: int) -> None:
        super().__init__(debug=False)

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

        # Handle initial greeting response
        status, message = self._handle_response()
        if not status:
            raise RuntimeError(f"Unexpected negative greeting from server: {message}")

    def _handle_response(self) -> tuple[bool, str]:
        response = self._read_until(self.terminator)
        if response is None:
            raise RuntimeError("Unexpected socket closure")
        if response.startswith("+OK"):
            try:
                return (True, response.split(" ", 1)[1])
            except IndexError:
                return (True, "")
        elif response.startswith("-ERR"):
            try:
                return (False, response.split(" ", 1)[1])
            except IndexError:
                return (False, "")
        else:
            raise RuntimeError(f"Unexpected response: `{response}`")

    def authenticate(self, user: str, password: str) -> None:
        status, message = self.pop3_USER(user)
        if not status:
            raise RuntimeError(f"Failed to authenticate with POP3 server: {message}")
        status, message = self.pop3_PASS(password)
        if not status:
            raise RuntimeError(f"Failed to authenticate with POP3 server: {message}")

    def close(self) -> None:
        self.pop3_QUIT()
        self.server_socket.close()    
        
    def read_data(self) -> str:        
        # Remove extraneous carriage returns and de-transparency according
        data = self._read_until(b"\r\n.\r\n")
        if data:
            mail_data = []
            for line in data.split(self._linesep):
                if line and line[0] == self._dotsep:
                    mail_data.append(line[1:])
                else:
                    mail_data.append(line)
            return self._newline.join(mail_data)
        else:
            raise RuntimeError("Unexpected socket closure")

    def pop3_USER(self, user: str) -> tuple[bool, str]:
        self.send_command(f"USER {user}")
        return self._handle_response()

    def pop3_PASS(self, passowrd: str) -> tuple[bool, str]:
        self.send_command(f"PASS {passowrd}")
        return self._handle_response()

    def pop3_STAT(self) -> tuple[int, int]:
        self.send_command("STAT")
        status, message = self._handle_response()
        if status:
            return (int(message.split()[0]), int(message.split()[1]))
        else:
            raise RuntimeError(f"Failed STAT command: {message}")
            
    def pop3_LIST(self, mail_n: int | None = None) -> list[tuple[int, int]]:
        if mail_n:
            self.send_command(f"LIST {mail_n}")
            status, message = self._handle_response()
            if status:
                return [(int(message.split()[0]), int(message.split()[1]))]
            else:
                raise RuntimeError(f"Failed LIST command: {message}")
        else:
            self.send_command("LIST")
            status, message = self._handle_response()
            if status:
                return [(int(line.split()[0]), int(line.split()[1])) for line in self.read_data().split(self._newline) if line]
            else:
                raise RuntimeError(f"Failed LIST command: {message}")

    def pop3_RETR(self, mail_n: int) -> str:
        self.send_command(f"RETR {mail_n}")
        status, message = self._handle_response()
        if status:
            return self.read_data()
        else:
            raise RuntimeError(f"Failed RETR command: {message}")

    def pop3_DELE(self, mail_n: int) -> str:
        self.send_command(f"DELE {mail_n}")
        response = self._read_until(self.terminator)
        if response is None:
            raise RuntimeError("Unexpected socket closure")
        return response

    def pop3_RSET(self) -> str:
        self.send_command("RSET")
        response = self._read_until(self.terminator)
        if response is None:
            raise RuntimeError("Unexpected socket closure")
        return response

    def pop3_QUIT(self) -> str:
        self.send_command("QUIT")
        response = self._read_until(self.terminator)
        if response is None:
            raise RuntimeError("Unexpected socket closure")
        return response


def mail_sending_cli(args: ProgramArgs) -> None:
    # Collect mail information
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
        smpt_client = SmptClient(args.ip_address, args.smtp_port)
    except Exception:
        print("Error creating smpt client")
        traceback.print_exc()
        return

    try:
        smpt_client.send_mail(sender, receiver, subject, message_str)
    except Exception:
        print("Error sending mail")
        traceback.print_exc()
        smpt_client.close()
        return

    smpt_client.close()

def mail_management_cli(args) -> None:
    user_name = input("Enter username: ")
    password = input("Enter password: ")


    try:
        pop3_client = Pop3Client(args.ip_address, args.pop3_port)
    except Exception:
        print("Error creating smpt client")
        traceback.print_exc()
        return

    try:
        pop3_client.authenticate(user_name, password)
    except RuntimeError as e:
        print(repr(e))
        pop3_client.close()
        return

    print(f"Succesfully authenticated as {user_name}!")

    # Retreive and list all mails
    mail_count = pop3_client.pop3_STAT()[0]
    print(f"--- {mail_count} mails in inbox ---")
    print(f"{'No.': <5} {'Sender': <20} {'Recieved at': <17} Subject")
    for mail_n in range(1, mail_count + 1):
        mail_data = pop3_client.pop3_RETR(mail_n)
        mail = parse_mail(mail_data)
        print(f"{mail_n: <5} {mail.sender: <20} {mail.received_date: <17} {mail.subject}")

    print("--------------------------")

    # Interactive commands
    while True:
        # Option menu
        print("--- POP3 Mail Management ---")
        print("")
        print("[1] STAT")
        print("[2] LIST")
        print("[3] RETR")
        print("[4] DELE")
        print("[5] RSET")
        print("[6] QUIT")

        while True:
            command_option = input("Enter an command option: ")
            if command_option in ["1", "2", "3", "4", "5", "6"]:
                break
            else:
                print("Invalid command option, please choose one of the command options.")

        if command_option == "1":
            result = pop3_client.pop3_STAT()
            print(f"{result[0]} Mails ({result[1]} octets)")
        elif command_option == "2":
            while True:
                try:
                    email_n = int(input("Enter a valid email number or 0 for all mails: "))
                    break
                except ValueError:
                    print("Not a valid number, try again.")
            try:            
                if email_n == 0:
                    result = pop3_client.pop3_LIST()
                else:
                    result = pop3_client.pop3_LIST(email_n)
                print("Mail list:")
                for mail in result:
                    print(f"{mail[0]} ({mail[1]} octets)")
            except RuntimeError as e:
                print(repr(e))
        elif command_option == "3":
            while True:
                try:
                    email_n = int(input("Enter a valid email number: "))
                    break
                except ValueError:
                    print("Not a valid number, try again.")
            try:            
                result = pop3_client.pop3_RETR(email_n)
                print("-- START OF MAIL ---")
                print(result)
                print("--- END OF MAIL ---")
            except RuntimeError as e:
                print(repr(e))
        elif command_option == "4":
            while True:
                try:
                    email_n = int(input("Enter a valid email number: "))
                    break
                except ValueError:
                    print("Not a valid number, try again.")
            print(pop3_client.pop3_DELE(email_n))
            
        elif command_option == "5":
            print(pop3_client.pop3_RSET())
        elif command_option == "6":
            print(pop3_client.pop3_QUIT())
            pop3_client.server_socket.close()
            return
            

def mail_searching_cli(args) -> None:
    pass
    user_name = input("Enter username: ")
    password = input("Enter password: ")


    try:
        pop3_client = Pop3Client(args.ip_address, args.pop3_port)
    except Exception:
        print("Error creating smpt client")
        traceback.print_exc()
        return

    try:
        pop3_client.authenticate(user_name, password)
    except RuntimeError as e:
        print(repr(e))
        pop3_client.close()
        return

    print(f"Succesfully authenticated as {user_name}!")


    # Collect all mails
    mails: list[Mail] = []
    mails_data: list[str] = []
    mail_count = pop3_client.pop3_STAT()[0]
    for mail_n in range(1, mail_count + 1):
        mail_data = pop3_client.pop3_RETR(mail_n)
        mails_data.append(mail_data)
        mail = parse_mail(mail_data)
        mails.append(mail)

    pop3_client.close()
        
    # Interactive commands
    while True:
        # Option menu
        print("--- POP3 Mail Search ---")
        print("")
        print("[1] Words/sentences")
        print("[2] Datatime")
        print("[3] Address")
        print("[4] Go back")

        while True:
            command_option = input("Enter an command option: ")
            if command_option in ["1", "2", "3", "4"]:
                break
            else:
                print("Invalid command option, please choose one of the command options.")    

        if command_option == "1":
            query = input("Enter the words/sentences to search for: ")
            for mail in mails_data:
                if query in mail:
                    print("-- START OF MAIL ---")
                    print(mail)
                    print("--- END OF MAIL ---")
        elif command_option == "2":
            query = input("Enter the time to search for (YYYY-MM-DD): ")
            for index, mail in enumerate(mails):
                if query == mail.received_date[:10]:
                    print("-- START OF MAIL ---")
                    print(mails_data[index])
                    print("--- END OF MAIL ---")
                    
        elif command_option == "3":
            query = input("Enter the address to search for: ")
            for index, mail in enumerate(mails):
                if query == mail.sender:
                    print("-- START OF MAIL ---")
                    print(mails_data[index])
                    print("--- END OF MAIL ---")
        elif command_option == "4":
            return
            
        
def user_interaction(args) -> None:
    # Ask for authentication information

    while True:
        # Option menu
        print("- Mail client - Please choose an option from the menu:")
        print("")
        print("[a] Mail sending")
        print("[b] Mail management")
        print("[c] Mail searching")
        print("[d] Exit")

        while True:
            menu_option = input("Enter an menu option: ")
            if menu_option in ["a", "A", "b", "B", "c", "C", "d", "D"]:
                break
            else:
                print("Invalid menu option, please choose one of the menu options.")

        match menu_option:
            case "a" | "A":
                mail_sending_cli(args)
            case "b" | "B":
                mail_management_cli(args)
            case "c" | "C":
                mail_searching_cli(args)
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
        "pop3_port", metavar="P", type=int, help="Port to connect mail POP3 server on."
    )

    parser.add_argument(
        "smtp_port", metavar="P", type=int, help="Port to connect mail SMTP server on."
    )
    args: ProgramArgs = parser.parse_args()  # type: ignore

    user_interaction(args)
