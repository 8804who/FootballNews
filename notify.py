"""Email the operator (ALERT_EMAIL, defaulting to the sender address).

CI calls this when a workflow fails; evaluate/gate.py calls alert() when it
holds a club's edition.

    python notify.py --subject "collect_news failed" --body "https://github.com/…"
"""

import argparse

from config import ALERT_EMAIL
from email_sender.smtp_sender import smtp_sender


def alert(subject: str, body: str) -> None:
    smtp_sender.send_email(ALERT_EMAIL, f"[FootballNews 알림] {subject}", body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Email the operator an alert")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", default="")
    args = parser.parse_args()
    alert(args.subject, args.body)
    print(f"Alert sent: {args.subject}")
