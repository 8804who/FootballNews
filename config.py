from yaml import load, Loader

### API KEYS, URLS ###
with open("api.yml", "r") as f:
    data = load(f, Loader=Loader)
    API_KEY = data["API_KEY"]
    URL = data["URL"]

### PROMPT ###
with open("prompt.yml", "r") as f:
    data = load(f, Loader=Loader)
    PROMPT = data["prompt"]

### TEAMS ###
with open("teams.yml", "r") as f:
    data = load(f, Loader=Loader)
    FBREF_TEAMS = data["fbref"]["teams"]
    FPL_TEAMS = data["FPL"]["teams"]
    FOTMOB_TEAMS = data["fotmob"]["teams"]