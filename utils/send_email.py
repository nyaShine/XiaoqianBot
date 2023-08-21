import os
import smtplib
from email.message import EmailMessage

from botpy import get_logger

from config import config

_log = get_logger()


class EmailSendingError(Exception):
    pass


def send_email(to_email, subject, body):
    smtp_server = config['email']['smtp_server']
    smtp_port = config['email']['smtp_port']
    from_email = os.environ.get('FROM_EMAIL')
    email_password = os.environ.get('EMAIL_PASSWORD')

    if not from_email or not email_password:
        raise EmailSendingError("FROM_EMAIL or EMAIL_PASSWORD environment variable is not set.")

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(from_email, email_password)
        server.send_message(msg)
        server.quit()
    except smtplib.SMTPException as e:
        _log.error(f"发送邮件到{to_email}时错误：{e}")
        raise EmailSendingError("Error sending email.")
    except Exception as e:
        _log.error(f"错误：{e}")
        raise EmailSendingError("Error occurred.")
