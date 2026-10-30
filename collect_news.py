import argparse
import json
import os
from datetime import datetime, timedelta

from config import FOTMOB_TEAMS, TEAMS
from scrappers.fotmob import fot_mob_crawler
from scrappers.news_rss import news_rss

# Each run re-collects the last few days, so a day whose run failed is picked
# up by the next one. The repeats are harmless: edition.py selects matches by
# kickoff time and keeps each one once.
LOOKBACK_DAYS = 3


def get_fotmob_data(team, start_date, end_date):
        fotmob_team = next((t for t in FOTMOB_TEAMS if t['name'] == team['name']), None)
        if not fotmob_team:
            print(f"Warning: Team '{team['name']}' not found in FOTMOB_TEAMS")
            return None

        target_team_id = fotmob_team['id']
        team_name = fotmob_team['name'].replace(" ", "_")

        raw_data = fot_mob_crawler.get_team_data(start_date, end_date, target_team_id)
        if raw_data is None:
            raise RuntimeError(f"[{team['name']}] could not capture FotMob team data")
        matches_output = fot_mob_crawler.generate_markdown_report(raw_data, 'matches')
        transfers_output = fot_mob_crawler.generate_markdown_report(raw_data, 'transfers')

        out_dir = f"datas/fotmob/{datetime.now().strftime('%Y%m%d')}"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/team_daily_report_{team_name}_matches.md", "w") as f:
            f.write(matches_output if matches_output else "")
        with open(f"{out_dir}/team_daily_report_{team_name}_transfers.md", "w") as f:
            f.write(transfers_output if transfers_output else "")
        with open(f"{out_dir}/team_daily_report_{team_name}_fixtures.json", "w") as f:
            json.dump(raw_data["fixtures"], f, ensure_ascii=False, indent=1)
        print(f"[{team['name']}] fotmob: wrote {len(raw_data['matches'])} match(es) + transfers + fixture list")

def get_news_rss_data(team):
    news_items = news_rss.get_transfer_news_rss(team['name'])
    markdown_output = news_rss.get_news_rss_markdown(news_items, team['name'])
    os.makedirs(f"datas/news_rss/{datetime.now().strftime('%Y%m%d')}", exist_ok=True)
    with open(f"datas/news_rss/{datetime.now().strftime('%Y%m%d')}/team_daily_report_{team['name'].replace(" ", "_")}.md", "w") as f:
        f.write(markdown_output if markdown_output else "There is no transfer news this week.")
    print(f"[{team['name']}] news_rss: wrote {len(news_items)} item(s)")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect FotMob + RSS data for each team")
    parser.add_argument("--team", help="Only collect this team (partial match)")
    args = parser.parse_args()

    today = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime('%Y%m%d')

    for team in TEAMS:
        if args.team and args.team.lower() not in team['name'].lower():
            continue
        get_fotmob_data(team, start_date, today)
        get_news_rss_data(team)
