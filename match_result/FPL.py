from datetime import datetime, timedelta
import requests

from config import FPL_TEAMS, URL

BASE_URL = URL["FPL"]


def fetch_bootstrap():
    # 1. 전체 데이터 조회
    bootstrap = requests.get(BASE_URL + "bootstrap-static/").json()

    teams = bootstrap["teams"]
    events = bootstrap["events"]
    return teams, events


def get_team_id(team_name: str, teams: list):
    '''
    팀 ID 조회
    
    Args:
        team_name: 팀 이름
        teams: 전체 팀 목록

    Returns:
        team_id: 팀 ID

    Raises:
        ValueError: 해당 팀의 경기 결과를 찾을 수 없을 때
    '''
    for team in teams:
        if team_name.lower() in team["name"].lower():
            return team["id"]
    raise ValueError(f"해당 팀의 경기 결과를 찾을 수 없습니다. {team_name}")


def get_recent_gameweek_ids(results: list, days: int = 7):
    '''
    최근 진행된 경기 Gameweek ID 조회

    Args:
        results: 전체 경기 Gameweek ID 목록

    Returns:
        recent_gameweek_ids: 최근 진행된 경기 Gameweek ID 목록
    '''
    start_datetime = datetime.utcnow() - timedelta(days=days)
    
    recent_gameweek_ids = [
        result["id"] for result in results 
        if result["finished"] and datetime.fromisoformat(result["deadline_time"]).replace(tzinfo=None) > start_datetime
    ]

    return recent_gameweek_ids


def get_fixtures(gameweek_ids: list):
    '''
    경기 결과 조회

    Args:
        gameweek_ids: 경기 Gameweek ID 목록

    Returns:
        all_fixtures: 전체 경기 결과 목록
    '''
    all_fixtures = []
    for gw_id in gameweek_ids:
        fixtures = requests.get(
            BASE_URL + f"fixtures/?event={gw_id}"
        ).json()
        all_fixtures.extend(fixtures)
    return all_fixtures


def get_team_fixtures(team_id: int, fixtures: list):
    '''
    팀 경기 결과 조회

    Args:
        team_id: 팀 ID
        fixtures: 전체 경기 결과 목록

    Returns:
        team_fixtures: 팀 경기 결과 목록
    '''
    return [
        f for f in fixtures
        if f["team_h"] == team_id or f["team_a"] == team_id
    ]


def parse_fixture(team_fixtures: list, team_id: int, team_name: str, teams: list) -> list:
    '''
    경기 결과 파싱

    Args:
        team_fixtures: 팀 경기 결과 목록
        team_id: 팀 ID
        team_name: 팀 이름
        teams: 전체 팀 목록

    Returns:
        game_results: 경기 결과 목록
    '''
    game_results = []
    for match in team_fixtures:
        is_home = match["team_h"] == team_id
        opponent_id = match["team_a"] if is_home else match["team_h"]

        opponent = next(t for t in teams if t["id"] == opponent_id)["name"]

        team_score = match["team_h_score"] if is_home else match["team_a_score"]
        opp_score = match["team_a_score"] if is_home else match["team_h_score"]

        venue = "Home" if is_home else "Away"

        result = '/n'.join([
            f"Gameweek: {match.get('event', 'N/A')}",
            f"Team: {team_name}",
            f"Opponent: {opponent}",
            f"Venue: {venue}",
            f"Score: {team_score} - {opp_score}",
            f"Finished: {match['finished']}"
        ])

        game_results.append(result)

    return game_results


def get_data(team_name: str):
    teams, results = fetch_bootstrap()
    team_id = get_team_id(team_name, teams)
    recent_gameweek_ids = get_recent_gameweek_ids(results)
    fixtures = get_fixtures(recent_gameweek_ids)
    team_fixtures = get_team_fixtures(team_id, fixtures)
    game_results = parse_fixture(team_fixtures, team_id, team_name, teams)
    print(game_results)

if __name__ == "__main__":
    for team in FPL_TEAMS:
        get_data(team["short_name"])