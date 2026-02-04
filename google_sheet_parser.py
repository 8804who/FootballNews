from google.oauth2.service_account import Credentials
import gspread

from config import GOOGLE_CLOUD, TEAMS


class GoogleSheetParser:
    def __init__(self, spreadsheet_url: str, worksheet_name: str):
        self.SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        self.SERVICE_ACCOUNT_FILE = "gen-lang-client.json"
        self.credentials = Credentials.from_service_account_file(self.SERVICE_ACCOUNT_FILE, scopes=self.SCOPES)
        self.gc = gspread.authorize(self.credentials)
        self.spreadsheet_url = GOOGLE_CLOUD["SPREADSHEET_URL"]
        self.doc = self.gc.open_by_url(spreadsheet_url)
        self.worksheet = self.doc.worksheet(worksheet_name)

    def get_all_records(self):
        return self.worksheet.get_all_records()

    def get_team_subscribers(self, team_name: str):
        subscribers = []
        records = self.get_all_records()
        for record in records:
            if record["Team"] == team_name:
                subscribers.append(record["email"])
        return subscribers

google_sheet_parser = GoogleSheetParser(GOOGLE_CLOUD["SPREADSHEET_URL"], "신청자 목록")