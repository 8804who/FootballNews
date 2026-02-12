import os
from datetime import datetime, timedelta, timezone

from config import FOTMOB_TEAMS, TEAMS
from email_sender.smtp_sender import smtp_sender
from google_sheet_parser import google_sheet_parser
from scrappers.fotmob import fot_mob_crawler
from scrappers.news_rss import news_rss
from summarizers.llm import llmSummarizer


def get_fotmob_data(team, start_date, end_date):
        fotmob_team = next((t for t in FOTMOB_TEAMS if t['name'] == team['name']), None)
        if not fotmob_team:
            print(f"Warning: Team '{team['name']}' not found in FOTMOB_TEAMS")
            return None
        
        target_team_id = fotmob_team['id']
        team_name = fotmob_team['name'].replace(" ", "_")
    
        raw_data = fot_mob_crawler.get_team_weekly_data(start_date, end_date, target_team_id)
        matches_output = fot_mob_crawler.generate_markdown_report(raw_data, 'matches')
        transfers_output = fot_mob_crawler.generate_markdown_report(raw_data, 'transfers')
        
        os.makedirs(f"datas/fotmob/{datetime.now().strftime('%Y%m%d')}", exist_ok=True)
        with open(f"datas/fotmob/{datetime.now().strftime('%Y%m%d')}/team_weekly_report_{team_name}_matches.md", "w") as f:
            f.write(matches_output if matches_output else "There is no match news this week.")
        with open(f"datas/fotmob/{datetime.now().strftime('%Y%m%d')}/team_weekly_report_{team_name}_transfers.md", "w") as f:
            f.write(transfers_output if transfers_output else "There is no transfer news this week.")

def get_news_rss_data(team):
    news_items = news_rss.get_transfer_news_rss(team['name'])
    markdown_output = news_rss.get_transfer_news_rss_markdown(news_items)
    os.makedirs(f"datas/news_rss/{datetime.now().strftime('%Y%m%d')}", exist_ok=True)
    with open(f"datas/news_rss/{datetime.now().strftime('%Y%m%d')}/team_weekly_report_{team['name'].replace(" ", "_")}.md", "w") as f:
        f.write(markdown_output if markdown_output else "There is no transfer news this week.")


def generate_newsletter(matches_data, transfers_data):
    newsletter = llmSummarizer.generate_newsletter(matches_data, transfers_data)
    return newsletter


def get_newsletter_subscribers(team):
    subscribers = google_sheet_parser.get_team_subscribers(team['name'])
    return subscribers


if __name__ == "__main__":
    for team in TEAMS:
        today = datetime.now(timezone.utc).strftime('%Y%m%d')
        start_date = datetime.strptime(today, '%Y%m%d').replace(tzinfo=timezone.utc) - timedelta(days=7)
        end_date = datetime.strptime(today, '%Y%m%d').replace(tzinfo=timezone.utc)
        get_fotmob_data(team, start_date, end_date)
        get_news_rss_data(team)

        matches_data = ""
        transfers_data = ""
        today = datetime.now().strftime('%Y%m%d')
        
        with open(f"datas/fotmob/{today}/team_weekly_report_{team['name'].replace(" ", "_")}_matches.md", "r") as f:
            matches_data = f.read()
            if matches_data == "There is no match news this week.":
                matches_data = None
        with open(f"datas/fotmob/{today}/team_weekly_report_{team['name'].replace(" ", "_")}_transfers.md", "r") as f:
            transfers_data = f.read()
            if transfers_data == "There is no transfer news this week.":
                transfers_data = None
        with open(f"datas/news_rss/{today}/team_weekly_report_{team['name'].replace(" ", "_")}.md", "r") as f:
            if transfers_data:
                transfers_data += f.read()
            else:
                transfers_data = f.read()
            if transfers_data == "There is no transfer news this week.":
                transfers_data = None

        newsletter = generate_newsletter(matches_data, transfers_data)
        os.makedirs(f"datas/newsletter/{today}", exist_ok=True)
        with open(f"datas/newsletter/{today}/team_weekly_report_{team['name'].replace(" ", "_")}.md", "w") as f:
            f.write(newsletter)

        subscribers = get_newsletter_subscribers(team)
        for subscriber in subscribers:
            print(f"Sending newsletter to {subscriber}")
            smtp_sender.send_email(subscriber, "Weekly Football Newsletter", newsletter)