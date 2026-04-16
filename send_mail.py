import os
from datetime import datetime, timezone, timedelta

from config import TEAMS
from email_sender.smtp_sender import smtp_sender
from google_sheet_parser import google_sheet_parser


def get_newsletter(today, team_name: str) -> str | None:
    newsletter_data = ""
    newsletter_path = f"datas/newsletter/{today}/newsletter_{team_name}.md"

    if not os.path.exists(newsletter_path):
        return None

    if os.path.exists(newsletter_path):
        with open(newsletter_path, "r") as f:
            newsletter_data += f.read() + "\n"

    return newsletter_data


if __name__ == "__main__":
    today = datetime.now(timezone.utc)
    end_date = today
    start_date = today - timedelta(days=7)
    today_str = today.strftime('%Y%m%d')
    start_date_str = start_date.strftime('%Y%m%d')

    for team in TEAMS:
        team_name = team["name"]

        newsletter = get_newsletter(today_str, team_name)

        subscribers = google_sheet_parser.get_team_subscribers(team_name)
        if not subscribers:
            print(f"[{team_name}] No subscribers found, skipping.")
            continue

        subject = f"[FootballNews] {team_name} 주간 뉴스레터 ({start_date_str}~{today_str})"
        for email in subscribers:
            smtp_sender.send_email(email, subject, newsletter)
            print(f"[{team_name}] Sent to {email}")

        print(f"[{team_name}] Done — {len(subscribers)} subscriber(s) notified.")
