from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import smtplib

from markdown_it import MarkdownIt

from config import SMTP
from email_sender.email_sender import EmailSender


EMAIL_STYLES = """
  body { margin: 0; padding: 0; background: #f4f4f5; }
  .wrap { max-width: 640px; margin: 0 auto; padding: 28px 24px; background: #ffffff;
          font-family: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic",
          "Helvetica Neue", Helvetica, Arial, sans-serif;
          line-height: 1.65; color: #1f2937; font-size: 16px; }
  .wrap h1 { font-size: 22px; line-height: 1.3; margin: 0 0 24px;
             padding-bottom: 14px; border-bottom: 2px solid #111827; color: #111827; }
  .wrap h2 { font-size: 18px; line-height: 1.35; margin: 32px 0 12px; color: #111827; }
  .wrap h3 { font-size: 16px; line-height: 1.4; margin: 20px 0 8px; color: #111827; }
  .wrap p, .wrap li { font-size: 16px; }
  .wrap p { margin: 0 0 14px; }
  .wrap ul, .wrap ol { margin: 0 0 14px; padding-left: 22px; }
  .wrap li { margin-bottom: 6px; }
  .wrap strong { color: #111827; }
  .wrap a { color: #1d4ed8; text-decoration: underline; }
  .wrap hr { border: 0; border-top: 1px solid #e5e7eb; margin: 24px 0; }
  .wrap table { border-collapse: collapse; width: 100%; margin: 0 0 18px;
                font-size: 15px; }
  .wrap th, .wrap td { border: 1px solid #e5e7eb; padding: 8px 10px;
                       text-align: left; vertical-align: top; }
  .wrap th { background: #f9fafb; font-weight: 600; }
"""


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
        html_body = self.convert_markdown_to_html(body, subject)
        message.attach(MIMEText(html_body, 'html'))
        text = message.as_string()
        server = smtplib.SMTP(self.smtp_server, self.smtp_port)
        server.starttls()
        server.login(self.smtp_username, self.smtp_password)
        server.sendmail(self.smtp_username, to, text)
        server.quit()

    def convert_markdown_to_html(self, markdown_text: str, title: str = "FootballNews"):
        md = MarkdownIt("commonmark").enable("table")
        body_html = md.render(markdown_text)
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