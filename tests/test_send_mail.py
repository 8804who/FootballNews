import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import send_mail
from email_sender.smtp_sender import smtp_sender
from google_sheet_parser import EMAIL_COLUMN, TEAM_COLUMN, GoogleSheetParser

RUN = datetime(2026, 10, 26, tzinfo=timezone.utc)


class FakeSheet(GoogleSheetParser):
    """The real matching logic over in-memory sheet rows (no Google calls)."""
    def __init__(self, records, unsubscribed=()):
        super().__init__("https://sheet.example", "신청자 목록")
        self.records, self.unsubscribed = records, set(unsubscribed)

    def get_all_records(self):
        return self.records

    def get_unsubscribed(self):
        return set(self.unsubscribed)


class FakeSender:
    def __init__(self, fail_for=()):
        self.sent, self.fail_for = [], set(fail_for)

    def send_email(self, to, subject, body, footer=None, headers=None):
        if to in self.fail_for:
            raise RuntimeError("SMTP connection dropped")
        self.sent.append({"to": to, "subject": subject, "footer": footer, "headers": headers})


def signup(team, email):
    return {TEAM_COLUMN: team, EMAIL_COLUMN: email}


class SendNewslettersTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)
        self.folder = Path("datas/newsletter/20261026")
        self.folder.mkdir(parents=True)
        for team in ("Arsenal", "Chelsea"):
            (self.folder / f"newsletter_{team}.md").write_text(f"# {team} · 주간 뉴스레터\n본문", encoding="utf-8")
        # Chelsea fails a check, which must not stop its email.
        (self.folder / "gate.json").write_text(json.dumps({"teams": {
            "Arsenal": {"flagged": False, "problems": [], "warnings": []},
            "Chelsea": {"flagged": True, "problems": ["missing from the scoreboard"], "warnings": []},
        }}), encoding="utf-8")
        self.sheet = FakeSheet([
            signup("Arsenal", "a1@example.com"),
            signup("arsenal ", "A1@example.com"),  # the same reader signed up twice
            signup("Arsenal", "gone@example.com"),
            signup("Chelsea", "c1@example.com"),
            signup("Leeds United", "nope@example.com"),
        ], unsubscribed={"gone@example.com"})

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def send(self, sender, **kwargs):
        return send_mail.send_newsletters(RUN, sheet=self.sheet, sender=sender, **kwargs)

    def test_each_reader_once_without_unsubscribed(self):
        sender = FakeSender()
        self.assertEqual(self.send(sender), [])
        self.assertEqual(sorted(s["to"] for s in sender.sent), ["a1@example.com", "c1@example.com"])
        arsenal = next(s for s in sender.sent if s["to"] == "a1@example.com")
        self.assertEqual(arsenal["subject"], "[FootballNews] Arsenal 주간 뉴스레터 (2026-10-19 ~ 2026-10-25)")

    def test_a_rerun_emails_nobody_twice(self):
        self.send(FakeSender())
        again = FakeSender()
        self.send(again)
        self.assertEqual(again.sent, [])

    def test_a_failed_send_fails_the_run_and_is_retried_next_time(self):
        problems = self.send(FakeSender(fail_for={"a1@example.com"}))
        self.assertEqual(len(problems), 1)
        self.assertNotIn("a1@example.com", problems[0])  # masked: workflow logs are public
        retry = FakeSender()
        self.send(retry)
        self.assertEqual([s["to"] for s in retry.sent], ["a1@example.com"])

    def test_an_edition_that_fails_a_check_is_still_sent(self):
        sender = FakeSender()
        self.send(sender)
        self.assertIn("c1@example.com", [s["to"] for s in sender.sent])

    def test_dry_run_sends_and_records_nothing(self):
        sender = FakeSender()
        self.send(sender, dry_run=True)
        self.assertEqual(sender.sent, [])
        self.assertFalse((self.folder / "sent.json").exists())

    def test_every_email_carries_an_unsubscribe_footer_and_header(self):
        sender = FakeSender()
        self.send(sender)
        self.assertIn("수신거부", sender.sent[0]["footer"])
        self.assertIn("mailto:", sender.sent[0]["headers"]["List-Unsubscribe"])

    def test_a_missing_newsletter_file_fails_the_run_instead_of_sending_a_blank_email(self):
        (self.folder / "newsletter_Arsenal.md").unlink()
        sender = FakeSender()
        problems = self.send(sender)
        self.assertEqual([s["to"] for s in sender.sent], ["c1@example.com"])  # other clubs still go out
        self.assertTrue(any("no newsletter file" in p for p in problems))


class MaskTest(unittest.TestCase):
    def test_logs_only_show_a_masked_address(self):
        self.assertEqual(send_mail.mask("jane.doe@example.com"), "j***@example.com")


class BuildMessageTest(unittest.TestCase):
    def test_message_names_the_sender_and_offers_unsubscribe(self):
        msg = smtp_sender.build_message(
            "reader@example.com", "[FootballNews] Arsenal 주간 뉴스레터", "# 제목\n\n본문",
            footer="[수신거부](mailto:x@example.com)",
            headers={"List-Unsubscribe": "<mailto:x@example.com?subject=unsubscribe>"},
        )
        self.assertTrue(msg["From"].startswith("FootballNews <"))
        self.assertEqual(msg["List-Unsubscribe"], "<mailto:x@example.com?subject=unsubscribe>")
        self.assertEqual([p.get_content_type() for p in msg.get_payload()], ["text/plain", "text/html"])
        html = msg.get_payload()[1].get_payload(decode=True).decode("utf-8")
        self.assertIn('<div class="footer">', html)
        self.assertIn("수신거부", html)


if __name__ == "__main__":
    unittest.main()
