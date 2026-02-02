from google.oauth2.service_account import Credentials
import gspread

from config import GOOGLE_CLOUD, TEAMS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SERVICE_ACCOUNT_FILE = "gen-lang-client.json"
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(credentials)
spreadsheet_url = GOOGLE_CLOUD["SPREADSHEET_URL"]
doc = gc.open_by_url(spreadsheet_url)

for team in TEAMS:
    worksheet = doc.worksheet(team['name'])
    col_a = worksheet.col_values(1)
    print(team["name"], col_a)