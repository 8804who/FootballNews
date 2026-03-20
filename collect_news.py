import os
from datetime import datetime, timedelta

from config import FOTMOB_TEAMS, TEAMS
from scrappers.fotmob import fot_mob_crawler
from scrappers.news_rss import news_rss


def get_fotmob_data(team, start_date, end_date):
        fotmob_team = next((t for t in FOTMOB_TEAMS if t['name'] == team['name']), None)
        if not fotmob_team:
            print(f"Warning: Team '{team['name']}' not found in FOTMOB_TEAMS")
            return None
        
        target_team_id = fotmob_team['id']
        team_name = fotmob_team['name'].replace(" ", "_")
    
        raw_data = fot_mob_crawler.get_team_data(start_date, end_date, target_team_id)
        matches_output = fot_mob_crawler.generate_markdown_report(raw_data, 'matches')
        transfers_output = fot_mob_crawler.generate_markdown_report(raw_data, 'transfers')
        
        os.makedirs(f"datas/fotmob/{datetime.now().strftime('%Y%m%d')}", exist_ok=True)
        with open(f"datas/fotmob/{datetime.now().strftime('%Y%m%d')}/team_daily_report_{team_name}_matches.md", "w") as f:
            f.write(matches_output if matches_output else "")
        with open(f"datas/fotmob/{datetime.now().strftime('%Y%m%d')}/team_daily_report_{team_name}_transfers.md", "w") as f:
            f.write(transfers_output if transfers_output else "")

def get_news_rss_data(team):
    news_items = news_rss.get_transfer_news_rss(team['name'])
    markdown_output = news_rss.get_transfer_news_rss_markdown(news_items)
    os.makedirs(f"datas/news_rss/{datetime.now().strftime('%Y%m%d')}", exist_ok=True)
    with open(f"datas/news_rss/{datetime.now().strftime('%Y%m%d')}/team_daily_report_{team['name'].replace(" ", "_")}.md", "w") as f:
        f.write(markdown_output if markdown_output else "There is no transfer news this week.")



if __name__ == "__main__":
    today = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')

    for team in TEAMS:
        get_fotmob_data(team, start_date, today)
        get_news_rss_data(team)