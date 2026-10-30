import argparse
import json
import os
from datetime import datetime, timezone

import edition
from config import TEAMS
from summarizers.llm import llmSummarizer


def load_weekly_data(team_name: str, start: datetime, end: datetime, run_date: datetime):
    """This edition's matches, transfers and headlines for one team — each
    match and headline once, selected by kickoff/publish time (edition.py)."""
    token = team_name.replace(" ", "_")

    match_blocks = edition.load_matches(token, start, end, run_date)
    matches_data = edition.matches_markdown(team_name, match_blocks, start, end)
    transfers_data = edition.transfers_markdown(team_name, edition.load_transfers(token, start, end, run_date))
    news_items = edition.load_news(token, team_name, start, end, run_date, edition.played_matches(match_blocks))

    return matches_data, transfers_data, news_items


def generate_edition(team_name: str, run_date: datetime, summarizer=llmSummarizer) -> str:
    """One team's newsletter for the edition of `run_date`. The LLM calls it
    made are left in summarizer.calls (evaluate/harness.py reuses this with
    other models and prompts)."""
    start, end = edition.edition_window(run_date)
    matches_data, transfers_data, news_items = load_weekly_data(team_name, start, end, run_date)
    summarizer.calls = []
    body = summarizer.generate_newsletter(matches_data, transfers_data, news_items)
    return f"# {team_name} · 주간 뉴스레터 ({edition.date_range_label(start, end)})\n\n" + body


def write_usage(folder: str, model: str, usage_by_team: dict) -> None:
    """Record each team's LLM calls (tokens, time) next to its newsletter, so
    the evaluation can report what the edition cost. Merges with an existing
    usage.json, so regenerating one team keeps the others."""
    path = os.path.join(folder, "usage.json")
    usage = {"teams": {}}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            usage = json.load(f)
    usage["model"] = model
    usage["teams"].update(usage_by_team)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(usage, f, indent=1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate this week's newsletter for each team")
    parser.add_argument("--date", help="Generate as if run on this day (YYYYMMDD); defaults to today (UTC)")
    parser.add_argument("--team", help="Only generate this team (partial match)")
    args = parser.parse_args()

    run_date = (
        datetime.strptime(args.date, "%Y%m%d").replace(tzinfo=timezone.utc)
        if args.date else datetime.now(timezone.utc)
    )
    start, end = edition.edition_window(run_date)
    run_str = run_date.strftime('%Y%m%d')
    folder = f"datas/newsletter/{run_str}"
    print(f"Edition {run_str}: matches and news from {edition.date_range_label(start, end)} (UTC)")

    usage_by_team = {}
    for team in TEAMS:
        team_name = team['name']
        if args.team and args.team.lower() not in team_name.lower():
            continue
        newsletter = generate_edition(team_name, run_date)

        os.makedirs(folder, exist_ok=True)
        output_path = f"{folder}/newsletter_{team_name.replace(' ', '_')}.md"
        with open(output_path, "w") as f:
            f.write(newsletter)
        usage_by_team[team_name] = llmSummarizer.calls

        print(f"Generated: {output_path}")

    if usage_by_team:
        write_usage(folder, llmSummarizer.model, usage_by_team)
