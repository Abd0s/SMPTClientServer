[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-24ddc0f5d75046c5622901739e7c5dd533143b0c8e959d652212380cedb1ea36.svg)](https://classroom.github.com/a/Mp-Kos87)

# This repositry contains a basic implementation of a Smtp server, POP3 server and a mail client to interact with the servers

# Requirements

Only tested on Python 3.10 and Windows

Install the required dependecies using pip:
sh```
pip install -r requirements.txt
```

# Setup
Add mail users by adding them to the `userinfo.txt` file in the `<username> <password` format and creating a <username>/mailbox.txt inside the users directory

## Usage

### SMTP server
Basic usage format:

sh```
python .\mailserver_smtp.py <ip_address> <port>
```

### POP3 server
Basic usage format:

sh```
python .\popserver.py <ip_address> <port>
```

### Mail client
Basic usage format:

sh```
python .\mail_client.py <ip_address> <pop3_port> <smtp_port>
```
