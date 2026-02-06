from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import base64
import smtplib

from config import SMTP
from email_sender.email_sender import EmailSender



class SMTPSender(EmailSender):
    def __init__(self):
        self.smtp_server = SMTP['SERVER']
        self.smtp_port = SMTP['PORT']
        self.smtp_username = SMTP['USERNAME']
        self.smtp_password = SMTP['PASSWORD']

    def send_email(self, to: str, subject: str, body: str):
        message = MIMEMultipart()
        message['From'] = self.smtp_username
        message['To'] = to
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))
        text = message.as_string()
        server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        server.starttls()
        server.login(self.smtp_username, self.smtp_password)
        server.sendmail(self.smtp_username, to, text)
        server.quit()

smtp_sender = SMTPSender()