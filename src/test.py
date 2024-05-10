import filelock
import mailbox_manager
import pathlib

# print(mailbox_manager.get_users(pathlib.Path(__file__).parent.parent.resolve() / "userinfo.txt"))
# print(mailbox_manager.validate_user(pathlib.Path(__file__).parent.parent.resolve() / "userinfo.txt", "abdulahad@mail.com", "password123"))
# print(mailbox_manager.validate_user(pathlib.Path(__file__).parent.parent.resolve() / "userinfo.txt", "abdulahad@mail.com", "passwordwdwdw123"))


# r = mailbox_manager.get_lock("abdulahad@myemail.com", pathlib.Path(__file__).parent.parent.resolve() / "users")

# try:
#     r.acquire(blocking=False)
#     input("Press enter to let go of lock")
# except filelock.Timeout:
#     print("Failed to get lock")
# finally:
#     r.release()

mailbox_manager.add_mail(
    pathlib.Path(__file__).parent.parent.resolve() / "users",
    "abdulahad@myemail.com",
    "From: <username>\nTo: <username>\nSubject: <subject string>\n<Message body - one or more lines>",
)
mailbox_manager.add_mail(
    pathlib.Path(__file__).parent.parent.resolve() / "users",
    "abdulahad@myemail.com",
    "From: <username>\nTo: <username>\nSubject: <subject string>\n<Message body - one or more lines>",
)
mailbox_manager.add_mail(
    pathlib.Path(__file__).parent.parent.resolve() / "users",
    "abdulahad@myemail.com",
    "From: <username>\nTo: <username>\nSubject: <subject string>\n<Message body - one or more lines>",
)


print(
    mailbox_manager.get_all_mails(
        pathlib.Path(__file__).parent.parent.resolve() / "users",
        "abdulahad@myemail.com",
    )
)

print(
    mailbox_manager.get_mail(
        pathlib.Path(__file__).parent.parent.resolve() / "users",
        "abdulahad@myemail.com",
        2,
    )
)

print(
    mailbox_manager.delete_mail(
        pathlib.Path(__file__).parent.parent.resolve() / "users",
        "abdulahad@myemail.com",
        2,
    )
)
print(
    mailbox_manager.get_all_mails(
        pathlib.Path(__file__).parent.parent.resolve() / "users",
        "abdulahad@myemail.com",
    )
)
