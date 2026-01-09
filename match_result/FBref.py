import requests
import time

from bs4 import BeautifulSoup
import pandas as pd

import config

BASE_URL = config.URL["fbref"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://fbref.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1"
}


def fetch_match_logs(team_id: str, season: str) -> pd.DataFrame:
    """
    FBref에서 특정 팀의 시즌별 경기 로그를 가져온다.
    """
    url = f"{BASE_URL}/en/squads/{team_id}/{season}/matchlogs/all_comps"
    
    # 세션을 사용하여 쿠키 유지
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # 요청 전 짧은 딜레이 추가
    time.sleep(1)
    
    resp = session.get(url)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # 먼저 직접 테이블을 찾아본다
    table = soup.find("table", id="matchlogs_all")
    
    if table:
        # 테이블을 직접 찾은 경우
        df = pd.read_html(str(table))[0]
        return df
    
    # 테이블이 주석 안에 있는 경우
    comments = soup.find_all(string=lambda text: isinstance(text, str) and "<table" in text)
    
    for c in comments:
        if 'id="matchlogs_all"' in c:
            df = pd.read_html(c)[0]
            return df
    
    # 두 방법 모두 실패한 경우, 페이지의 모든 테이블을 시도
    all_tables = soup.find_all("table")
    if all_tables:
        # matchlogs 관련 테이블 찾기
        for table in all_tables:
            if "matchlogs" in str(table.get("id", "")).lower():
                df = pd.read_html(str(table))[0]
                return df
    
    # 마지막으로 pandas가 직접 HTML에서 읽기 시도
    try:
        dfs = pd.read_html(resp.text, attrs={"id": "matchlogs_all"})
        if dfs:
            return dfs[0]
    except Exception as e:
        print(f"Failed to read table with pandas: {e}")
    
    # 디버깅: 페이지에 어떤 테이블이 있는지 확인
    all_table_ids = [t.get("id", "no-id") for t in soup.find_all("table")]
    print(f"Found tables with IDs: {all_table_ids}")
    
    raise RuntimeError("Match log table not found")


def clean_match_logs(df: pd.DataFrame) -> pd.DataFrame:
    """
    뉴스레터에 필요한 최소한의 컬럼만 남긴다.
    """
    df = df.rename(columns={
        "Date": "date",
        "Comp": "competition",
        "Opponent": "opponent",
        "Venue": "venue",
        "Result": "result",
        "GF": "goals_for",
        "GA": "goals_against",
        "Poss": "possession"
    })

    keep_cols = [
        "date",
        "competition",
        "opponent",
        "venue",
        "result",
        "goals_for",
        "goals_against",
        "possession"
    ]

    return df[keep_cols]


def get_recent_matches(df: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    return df.sort_values("date", ascending=False).head(n)


if __name__ == "__main__":
    TEAM_ID = teams.fbref.teams[0].id
    SEASON = "2024-2025"

    raw_df = fetch_match_logs(TEAM_ID, SEASON)
    clean_df = clean_match_logs(raw_df)
    recent = get_recent_matches(clean_df, n=2)

    print(recent)
    recent.to_csv("recent_matches.csv", index=False)
    time.sleep(2)  # 요청 간 딜레이
