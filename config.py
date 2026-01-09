from yaml import load, Loader

### API KEYS, URLS ###
with open("api.yaml", "r") as f:
    data = load(f, Loader=Loader)
    API_KEY = data["API_KEY"]
    URL = data["URL"]

### TEAMS ###
with open("teams.yaml", "r") as f:
    data = load(f, Loader=Loader)
    API_FOOTBALL_TEAMS = data["api_football"]["teams"]
    FBREF_TEAMS = data["fbref"]["teams"]
    FPL_TEAMS = data["FPL"]["teams"]