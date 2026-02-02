from yaml import load, Loader

### API KEYS, URLS ###
with open("api.yml", "r") as f:
    data = load(f, Loader=Loader)
    API_KEY = data["API_KEY"]
    URL = data["URL"]
    GOOGLE_CLOUD = data["GOOGLE_CLOUD"]

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