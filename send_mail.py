import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import quote

import edition
from config import NEWSLETTER, SMTP, TEAMS
from email_sender.smtp_sender import smtp_sender
from google_sheet_parser import google_sheet_parser


def get_newsletter(today, team_name: str) -> str | None:

    team_name_normalized = team_name.replace(" ", "_")

    newsletter_data = ""
    newsletter_path = f"datas/newsletter/{today}/newsletter_{team_name_normalized}.md"

    if not os.path.exists(newsletter_path):
        return ""

    if os.path.exists(newsletter_path):
        with open(newsletter_path, "r") as f:
            newsletter_data += f.read() + "\n"

    return newsletter_data


def mask(email: str) -> str:
    """'j***@gmail.com' — this repo is public, and so are its workflow logs."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


def recipient_key(email: str) -> str:
    """What sent.json records instead of the address itself."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def unsubscribe_link(email: str) -> str:
    url = NEWSLETTER.get("unsubscribe_url")
    if url:
        return url.replace("{email}", quote(email))
    body = f"{email} 주소의 수신거부를 요청합니다."
    return f"mailto:{SMTP['USERNAME']}?subject={quote('FootballNews 수신거부')}&body={quote(body)}"


def footer_for(team_name: str, email: str) -> str:
    links = [f"[수신거부]({unsubscribe_link(email)})"]
    if NEWSLETTER.get("signup_url"):
        links.append(f"[팀 변경]({NEWSLETTER['signup_url']})")
    links.append(f"[의견 보내기](mailto:{SMTP['USERNAME']}?subject={quote('FootballNews 의견')})")
    return (
        f"FootballNews **{team_name}** 주간 뉴스레터를 신청하셔서 받으신 메일입니다.\n\n"
        + " · ".join(links)
    )


def list_unsubscribe_header(email: str) -> str:
    """Lets Gmail/Apple Mail show their own 'Unsubscribe' button."""
    targets = [f"<mailto:{SMTP['USERNAME']}?subject=unsubscribe>"]
    if NEWSLETTER.get("unsubscribe_url"):
        targets.append(f"<{unsubscribe_link(email)}>")
    return ", ".join(targets)


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def send_newsletters(run_date, dry_run=False, sheet=google_sheet_parser, sender=smtp_sender):
    """Email each team's edition for `run_date` to its subscribers. Returns
    the problems that should fail the run (send errors, missing files).

    evaluate/gate.py's checks don't stop a send: they're shown on the
    dashboard. Only a missing file or a failed send is an error here."""
    today_str = run_date.strftime('%Y%m%d')
    start, end = edition.edition_window(run_date)
    folder = f"datas/newsletter/{today_str}"

    # Recipients already sent this edition (sha256 per team), so a re-run
    # after a partial failure only reaches the ones that didn't get it.
    sent_path = f"{folder}/sent.json"
    sent = _load_json(sent_path)

    records = sheet.get_all_records()
    unsubscribed = sheet.get_unsubscribed()
    for answer, count in sheet.get_unmatched_teams(records).items():
        print(f"⚠ {count} sign-up(s) chose '{answer}', which matches no configured team — "
              "they receive nothing until the answer or teams.yml aliases are fixed.")

    failures = []
    for team in TEAMS:
        team_name = team["name"]

        subscribers = sheet.get_team_subscribers(team_name, records, unsubscribed)
        if not subscribers:
            print(f"[{team_name}] No subscribers found, skipping.")
            continue

        newsletter = get_newsletter(today_str, team_name)
        if not newsletter:
            failures.append(f"[{team_name}] no newsletter file in {folder}")
            print(failures[-1])
            continue

        subject = f"[FootballNews] {team_name} 주간 뉴스레터 ({edition.date_range_label(start, end)})"
        already = set(sent.get(team_name, []))
        delivered = 0
        for email in subscribers:
            key = recipient_key(email)
            if key in already:
                print(f"[{team_name}] Already sent to {mask(email)}, skipping")
                continue
            if dry_run:
                print(f"[{team_name}] Would send to {mask(email)}: {subject}")
                delivered += 1
                continue
            try:
                sender.send_email(
                    email, subject, newsletter,
                    footer=footer_for(team_name, email),
                    headers={"List-Unsubscribe": list_unsubscribe_header(email)},
                )
            except Exception as e:
                failures.append(f"[{team_name}] {mask(email)}: {e}")
                print(f"Email send failed|{mask(email)}|{team_name}\nError:{e}")
                continue
            sent.setdefault(team_name, []).append(key)
            _save_json(sent_path, sent)  # after every send, so a crash can't cause repeats
            delivered += 1
            print(f"[{team_name}] Sent to {mask(email)}")

        print(f"[{team_name}] Done — {delivered} subscriber(s) {'would be ' if dry_run else ''}notified.")

    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Email this week's newsletters to each team's subscribers")
    parser.add_argument("--date", help="Send the newsletters generated on this day (YYYYMMDD); defaults to today (UTC)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be sent, without sending anything")
    args = parser.parse_args()

    run_date = (
        datetime.strptime(args.date, "%Y%m%d").replace(tzinfo=timezone.utc)
        if args.date else datetime.now(timezone.utc)
    )
    failures = send_newsletters(run_date, dry_run=args.dry_run)

    if failures:
        print(f"\n{len(failures)} problem(s):")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)
