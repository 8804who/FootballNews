import requests
from typing import Dict, List

from config import API_KEY, URL

API_KEY = API_KEY["api_football"]
BASE_URL = URL["api_football"]

HEADERS = {
    "x-apisports-key": API_KEY
}


def api_get(endpoint: str, params: Dict = None) -> Dict:
    url = f"{BASE_URL}/{endpoint}"
    response = requests.get(url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()


def get_team_id(team_name: str) -> int:
    data = api_get(
        "teams",
        params={"search": team_name}
    )
    return data["response"][0]["team"]["id"]


def get_recent_fixtures(team_id: int, last: int = 5) -> List[Dict]:
    data = api_get(
        "fixtures",
        params={
            "team": team_id,
            "season": 2024,
            # "last": last
        }
    )
    print(data)
    return data["response"]


def parse_fixture(fixture: Dict) -> Dict:
    return {
        "date": fixture["fixture"]["date"],
        "home": fixture["teams"]["home"]["name"],
        "away": fixture["teams"]["away"]["name"],
        "score": {
            "home": fixture["goals"]["home"],
            "away": fixture["goals"]["away"]
        },
        "status": fixture["fixture"]["status"]["short"]
    }


def get_lineups(fixture_id: int) -> List[Dict]:
    data = api_get(
        "fixtures/lineups",
        params={"fixture": fixture_id}
    )
    return data["response"]


def parse_lineup(lineup: Dict) -> Dict:
    return {
        "team": lineup["team"]["name"],
        "formation": lineup["formation"],
        "starting_xi": [
            p["player"]["name"]
            for p in lineup["startXI"]
        ],
        "subs": [
            p["player"]["name"]
            for p in lineup["substitutes"]
        ]
    }


def get_player_stats(fixture_id: int, team_id: int) -> List[Dict]:
    data = api_get(
        "fixtures/players",
        params={
            "fixture": fixture_id,
            "team": team_id
        }
    )
    return data["response"][0]["players"]


def parse_player_minutes(players: List[Dict]) -> List[Dict]:
    return [
        {
            "name": p["player"]["name"],
            "minutes": p["statistics"][0]["games"]["minutes"]
        }
        for p in players
    ]


def collect_team_weekly_data(team_name: str):
    team_id = get_team_id(team_name)
    fixtures = get_recent_fixtures(team_id, last=2)

    results = []

    for f in fixtures:
        fixture_id = f["fixture"]["id"]

        result = parse_fixture(f)
        lineups = get_lineups(fixture_id)
        players = get_player_stats(fixture_id, team_id)

        result["lineup"] = [
            parse_lineup(l) for l in lineups
            if l["team"]["id"] == team_id
        ]
        result["player_minutes"] = parse_player_minutes(players)

        results.append(result)

    return results


if __name__ == "__main__":
    team_name = "Manchester United"
    results = collect_team_weekly_data(team_name)
    print(results)

# url = "https://v3.football.api-sports.io/teams?id=33"

# payload={}
# headers = {
#   'x-apisports-key': API_KEY,
# }

# response = requests.request("GET", url, headers=headers, data=payload)

# print(response.text)