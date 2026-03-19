import os
from yaml import load, Loader

### API KEYS, URLS ###
if os.path.exists("api.yml"):
    with open("api.yml", "r") as f:
        data = load(f, Loader=Loader)
        API_KEY = data["API_KEY"]
        URL = data["URL"]
        GOOGLE_CLOUD = data["GOOGLE_CLOUD"]
        SMTP = data["SMTP"]
else:
    API_KEY = {"OPENAI": os.environ["OPENAI_API_KEY"]}
    URL = {
        "FPL": os.environ.get("URL_FPL", "https://fantasy.premierleague.com/api/"),
        "fbref": os.environ.get("URL_FBREF", "https://fbref.com/"),
    }
    GOOGLE_CLOUD = {
        "EMAIL": os.environ["GOOGLE_CLOUD_EMAIL"],
        "SPREADSHEET_URL": os.environ["GOOGLE_CLOUD_SPREADSHEET_URL"],
    }
    SMTP = {
        "SERVER": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
        "PORT": int(os.environ.get("SMTP_PORT", "587")),
        "USERNAME": os.environ["SMTP_USERNAME"],
        "PASSWORD": os.environ["SMTP_PASSWORD"],
    }

### EXAMPLE ###
with open("example.yml", "r") as f:
    data = load(f, Loader=Loader)
    EXAMPLE = data

### PROMPT ###
with open("prompt.yml", "r") as f:
    data = load(f, Loader=Loader)
    PROMPT = data

### TEAMS ###
with open("teams.yml", "r") as f:
    data = load(f, Loader=Loader)
    FBREF_TEAMS = data["fbref"]["teams"]
    FPL_TEAMS = data["FPL"]["teams"]
    FOTMOB_TEAMS = data["fotmob"]["teams"]

### SETTING ###
with open("setting.yml", "r") as f:
    data = load(f, Loader=Loader)
    TEAMS = data["teams"]
    MODEL = data["model"]
