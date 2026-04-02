import os
from datetime import datetime, timedelta, timezone

from config import TEAMS
from summarizers.llm import llmSummarizer


def load_weekly_data(team_name: str, start_date: datetime, end_date: datetime):
    matches_data = ""
    transfers_data = ""

    team_name_normalized = team_name.replace(" ", "_")
    current = start_date
    while current < end_date:
        date_str = current.strftime('%Y%m%d')

        matches_path = f"datas/fotmob/{date_str}/team_daily_report_{team_name_normalized}_matches.md"
        transfers_path = f"datas/fotmob/{date_str}/team_daily_report_{team_name_normalized}_transfers.md"

        if os.path.exists(matches_path):
            with open(matches_path, "r") as f:
                matches_data += f.read() + "\n"

        if os.path.exists(transfers_path):
            with open(transfers_path, "r") as f:
                transfers_data += f.read() + "\n"

        current += timedelta(days=1)

    return matches_data.strip(), transfers_data.strip()


if __name__ == "__main__":
    today = datetime.now(timezone.utc)
    end_date = today
    start_date = today - timedelta(days=7)
    today_str = today.strftime('%Y%m%d')

    for team in TEAMS:
        team_name = team['name']
        matches_data, transfers_data = load_weekly_data(team_name, start_date, end_date)

        newsletter = llmSummarizer.generate_newsletter(matches_data, transfers_data)

        os.makedirs(f"datas/newsletter/{today_str}", exist_ok=True)
        output_path = f"datas/newsletter/{today_str}/newsletter_{team_name.replace(' ', '_')}.md"
        with open(output_path, "w") as f:
            f.write(newsletter)

        print(f"Generated: {output_path}")
