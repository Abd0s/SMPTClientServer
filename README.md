# About
A basic implementation of a Smtp server, POP3 server and a mail client to interact with the servers.

# Requirements

This project has only tested on Python 3.10 and Windows.

Install the required dependencies using pip:
```bash
pip install -r requirements.txt
```

# Setup
Add mail users by adding them to the `userinfo.txt` file in the `<username> <password` format and creating a `users/<username>/mailbox.txt`.

## Usage

### SMTP server
Basic usage format:

```bash
python .\mailserver_smtp.py <ip_address> <port>
```

### POP3 server
Basic usage format:

```bash
python .\popserver.py <ip_address> <port>
```

### Mail client
Basic usage format:

```bash
python .\mail_client.py <ip_address> <pop3_port> <smtp_port>
```
