"""Module to manage the local email storage

This module manages the local email storage in the following defined structure:

Note: This implementation lacks proper exception handling and format validation.

- A userfile containing all valid users. Every line specifies a user in the folllowing format:
<username> <SPACE> <password>

- A users directory containing directories for all registered users. Each directory containing
a mailbox.txt file representing the users mailbox and containing the users mails each seperated
by a full stop in the following format:
From: <username>
To: <username>
Subject: <subject string>
Received: <time at which received, in data : hour: minute >
<Message body - one or more lines>
"""

import filelock
import pathlib
import datetime


# USER MANAGEMENT
def get_users(usersfile: pathlib.Path) -> list[str]:
    """Returns all users registered in the userfile

    Args:
        userfile: Path to the userfile containing the registered users.

    Returns:
        A list containing all the registered users
    """
    with open(usersfile, "r") as f:
        return [entry.strip().split(" ")[0] for entry in f.readlines()]


def validate_user(usersfile: pathlib.Path, username: str, password: str) -> bool:
    """Validates that the given username and password pair

    Validates that the given username and password pair correspond to an valid
    user entry in the given userfile.

    Args:
        userfile: Path to the userfile containing the registered users.
        username: The username of the user to valdiate.
        password: The pasword of the user to validate.

    Returns:
        Indicates whether the the given user was able to be validated or not.
    """
    with open(usersfile, "r") as f:
        return [username, password] in [
            entry.strip().split(" ") for entry in f.readlines()
        ]


# MAILBOX MANAGEMENT
def get_lock(username: str, users: pathlib.Path) -> filelock.FileLock:
    """Gets a lock for the mailbox for the given user

    Args:
        username: The username of mailbox to aquire the lock.
        users: The path to the users mailboxes directory.
    """
    return filelock.FileLock(users / username / "mailbox.txt.lock")


def add_mail(users: pathlib.Path, rcpt: str, mail: str) -> None:
    # Add `Received: ` field
    mail_lines = mail.splitlines()
    now = datetime.datetime.now()
    received_line = f"Received: {now.year:02d}-{now.month:02d}-{now.day:02d}:{now.hour:02d}:{now.minute:02d}"
    mail_lines.insert(3, received_line)
    modified_mail = "\n".join(mail_lines)

    # Append mail to receipt's mailboxes
    with open(users / pathlib.Path(rcpt) / "mailbox.txt", "a") as f:
        f.write(modified_mail)
        f.write("\n.\n")


def get_all_mails(users: pathlib.Path, username: str) -> list[str]:
    with open(users / pathlib.Path(username) / "mailbox.txt", "r") as f:
        return [mail for mail in f.read().split("\n.\n") if mail]


def get_mail(users: pathlib.Path, username: str, mail_n: int) -> str | None:
    return get_all_mails(users, username)[mail_n]


def delete_mail(users: pathlib.Path, username: str, mail_n: list[int]) -> None:
    mails = get_all_mails(users, username)
    for mail in mail_n:
        mails.pop(mail)

    with open(users / pathlib.Path(username) / "mailbox.txt", "w") as f:
        f.write("\n.\n".join(mails))
        f.write("\n.\n")
