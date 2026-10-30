from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import smtplib

from markdown_it import MarkdownIt

from config import SMTP
from email_sender.email_sender import EmailSender


EMAIL_STYLES = """
  body { margin: 0; padding: 0; background: #d8d2c4; }
  .wrap { max-width: 640px; margin: 0 auto; padding: 28px 24px; background: #f4f0e6;
          font-family: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic",
          "Helvetica Neue", Helvetica, Arial, sans-serif;
          line-height: 1.7; color: #2b2a26; font-size: 16px; }
  .wrap h1 { margin: -28px -24px 24px; padding: 22px 24px 18px; font-size: 22px;
             line-height: 1.3; font-weight: 700; background: #14204d; color: #f4f0e6;
             border-bottom: 6px solid #c8a24a; }
  .wrap h2 { display: inline-block; font-size: 13px; line-height: 1.4; margin: 32px 0 14px;
             padding-bottom: 8px; border-bottom: 2px solid #c8a24a; color: #14204d;
             text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
  .wrap h2 + p strong { display: block; font-size: 20px; line-height: 1.4; color: #14204d; }
  .wrap h3 { font-size: 16px; line-height: 1.4; margin: 20px 0 8px; color: #14204d; }
  .wrap p, .wrap li { font-size: 16px; }
  .wrap p { margin: 0 0 14px; }
  .wrap ul, .wrap ol { margin: 0 0 14px; padding-left: 22px; }
  .wrap li { margin-bottom: 6px; }
  .wrap strong { color: #14204d; }
  .wrap a { color: #14204d; text-decoration: underline; }
  .wrap hr { border: 0; border-top: 1px dotted #b8ac8e; margin: 28px 0; }
  .wrap table { border-collapse: collapse; width: 100%; margin: 4px 0 20px;
                font-size: 15px; }
  .wrap th { background: #14204d; color: #c8a24a; font-weight: 700; font-size: 12px;
             letter-spacing: 0.5px; text-transform: uppercase; padding: 10px 12px;
             text-align: left; white-space: nowrap; }
  .wrap td { border-bottom: 1px solid #d8d2c4; padding: 12px; text-align: left;
             vertical-align: top; }
  .wrap .footer { margin-top: 32px; padding-top: 14px; border-top: 1px dotted #b8ac8e; }
  .wrap .footer p { font-size: 13px; line-height: 1.6; margin: 0 0 6px; }
"""

SENDER_NAME = "FootballNews"


class SMTPSender(EmailSender):
    def __init__(self):
        self.smtp_server = SMTP['SERVER']
        self.smtp_port = SMTP['PORT']
        self.smtp_username = SMTP['USERNAME']
        self.smtp_password = SMTP['PASSWORD']

    def build_message(self, to: str, subject: str, body: str, footer: str = None, headers: dict = None):
        # Plain-text + HTML alternatives: HTML-only mail is a spam signal, and
        # the markdown reads fine as text.
        message = MIMEMultipart('alternative')
        message['From'] = formataddr((SENDER_NAME, self.smtp_username))
        message['To'] = to
        message['Subject'] = subject
        for name, value in (headers or {}).items():
            message[name] = value
        plain = f"{body}\n\n---\n{footer}" if footer else body
        message.attach(MIMEText(plain, 'plain', 'utf-8'))
        message.attach(MIMEText(self.convert_markdown_to_html(body, subject, footer), 'html', 'utf-8'))
        return message

    def send_email(self, to: str, subject: str, body: str, footer: str = None, headers: dict = None):
        text = self.build_message(to, subject, body, footer, headers).as_string()
        server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        server.starttls()
        server.login(self.smtp_username, self.smtp_password)
        server.sendmail(self.smtp_username, to, text)
        server.quit()

    def convert_markdown_to_html(self, markdown_text: str, title: str = "FootballNews", footer: str = None):
        md = MarkdownIt("commonmark").enable("table")
        body_html = md.render(markdown_text)
        if footer:
            body_html += f"<div class=\"footer\">\n{md.render(footer)}</div>\n"
        return (
            "<!doctype html>\n"
            "<html lang=\"ko\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"  <title>{title}</title>\n"
            f"  <style>{EMAIL_STYLES}</style>\n"
            "</head>\n"
            "<body>\n"
            f"  <div class=\"wrap\">\n{body_html}  </div>\n"
            "</body>\n"
            "</html>\n"
        )

smtp_sender = SMTPSender()