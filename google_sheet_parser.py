import os
import re
from collections import Counter

from google.oauth2.service_account import Credentials
import google.auth
import gspread

from config import GOOGLE_CLOUD
from team_names import canonical

TEAM_COLUMN = "어떤 팀의 소식을 받아보고 싶나요?"
EMAIL_COLUMN = "뉴스 레터를 수신할 이메일을 입력해주세요."
# Optional worksheet of addresses that asked to stop receiving the newsletter
# (any column; every cell that looks like an email address counts).
UNSUBSCRIBE_SHEET = "수신거부"
_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class GoogleSheetParser:
    def __init__(self, spreadsheet_url: str, worksheet_name: str):
        self.SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        self.SERVICE_ACCOUNT_FILE = "gen-lang-client.json"
        self.spreadsheet_url = spreadsheet_url
        self.worksheet_name = worksheet_name
        self._doc = None

    @property
    def doc(self):
        """Opened on first use, so importing this module doesn't need Google."""
        if self._doc is None:
            if os.path.exists(self.SERVICE_ACCOUNT_FILE):
                credentials = Credentials.from_service_account_file(self.SERVICE_ACCOUNT_FILE, scopes=self.SCOPES)
            else:
                credentials, _ = google.auth.default(scopes=self.SCOPES)
            self._doc = gspread.authorize(credentials).open_by_url(self.spreadsheet_url)
        return self._doc

    @property
    def worksheet(self):
        return self.doc.worksheet(self.worksheet_name)

    def get_all_records(self):
        return self.worksheet.get_all_records()

    def get_unsubscribed(self) -> set:
        """Lower-cased addresses in the "수신거부" worksheet (empty if it doesn't exist)."""
        try:
            rows = self.doc.worksheet(UNSUBSCRIBE_SHEET).get_all_values()
        except gspread.exceptions.WorksheetNotFound:
            return set()
        return {cell.strip().lower() for row in rows for cell in row if _EMAIL_RE.fullmatch(cell.strip())}

    def get_team_subscribers(self, team_name: str, records=None, unsubscribed=None):
        """Unique addresses whose chosen team is `team_name` under any spelling
        (teams.yml aliases), minus anyone who unsubscribed."""
        records = self.get_all_records() if records is None else records
        unsubscribed = self.get_unsubscribed() if unsubscribed is None else unsubscribed
        subscribers = []
        for record in records:
            if canonical(str(record[TEAM_COLUMN])) != team_name:
                continue
            email = str(record[EMAIL_COLUMN]).strip()
            if email and email.lower() not in unsubscribed and email.lower() not in {s.lower() for s in subscribers}:
                subscribers.append(email)
        return subscribers

    def get_unmatched_teams(self, records=None) -> Counter:
        """Team answers that resolve to no configured club → number of sign-ups.
        These subscribers get nothing until the answer (or teams.yml) is fixed."""
        records = self.get_all_records() if records is None else records
        return Counter(
            str(r[TEAM_COLUMN]).strip() for r in records
            if str(r[TEAM_COLUMN]).strip() and canonical(str(r[TEAM_COLUMN])) is None
        )

google_sheet_parser = GoogleSheetParser(GOOGLE_CLOUD["SPREADSHEET_URL"], "신청자 목록")
