from datetime import datetime
import requests
import time
import os


from bs4 import BeautifulSoup
import pandas as pd

import config

BASE_URL = config.URL["fbref"]
teams = config.FBREF_TEAMS


class FBrefScraper:
    def __init__(self):
        self.base_url = BASE_URL
        self.HEADERS = {
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


    def get_match_logs(self, team_id: str, season: str) -> pd.DataFrame:
        """
        FBref에서 특정 팀의 시즌별 경기 로그를 가져온다.
        """
        url = f"{self.base_url}/en/squads/{team_id}/{season}/matchlogs/all_comps"
        
        # 세션을 사용하여 쿠키 유지
        session = requests.Session()
        session.headers.update(self.HEADERS)
        
        # 요청 전 짧은 딜레이 추가
        time.sleep(5)
        
        resp = session.get(url)
        resp.raise_for_status()

        if not os.path.exists(f"datas/fbref/{datetime.now().strftime('%Y%m%d')}/match_logs_{team_id}_{season}.html"):
            soup = BeautifulSoup(resp.text, "lxml")
            os.makedirs(f"datas/fbref/{datetime.now().strftime('%Y%m%d')}", exist_ok=True)
            with open(f"datas/fbref/{datetime.now().strftime('%Y%m%d')}/match_logs_{team_id}_{season}.html", "w") as f:
                f.write(soup.prettify())
        else:
            with open(f"datas/fbref/{datetime.now().strftime('%Y%m%d')}/match_logs_{team_id}_{season}.html", "r") as f:
                soup = BeautifulSoup(f.read(), "lxml")

        return soup


    def parse_match_logs(self, soup: BeautifulSoup) -> pd.DataFrame:
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


    def clean_match_logs(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        뉴스레터에 필요한 컬럼만 추출
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


    def get_recent_matches(self, team_id: str, season: str, n: int = 2) -> pd.DataFrame:
        """
        최근 경기 결과 조회
        """

        soup = self.get_match_logs(team_id, season)
        df = self.parse_match_logs(soup)
        df = self.clean_match_logs(df)
        return df.sort_values("date", ascending=False).head(n).reset_index(drop=True)


if __name__ == "__main__":
    fbref_scraper = FBrefScraper()
    for team in teams[1:]:
        TEAM_ID = team["id"]
        SEASON = "2025-2026"

        recent = fbref_scraper.get_recent_matches(TEAM_ID, SEASON, n=2)

        print(recent)
        time.sleep(30)  # 요청 간 딜레이


