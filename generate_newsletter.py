import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import edition
from config import TEAMS
from summarizers import blocks
from summarizers.llm import llmSummarizer


def load_weekly_data(team_name: str, start: datetime, end: datetime, run_date: datetime):
    """This edition's matches, transfers and stories for one team — each
    match and story once, selected by kickoff/publish time (edition.py)."""
    token = team_name.replace(" ", "_")

    match_blocks = edition.load_matches(token, start, end, run_date)
    fixtures = edition.load_fixtures(token, start, run_date)
    matches_data = edition.matches_markdown(team_name, match_blocks, start, end, fixtures)
    transfers_data = edition.transfers_markdown(team_name, edition.load_transfers(token, start, end, run_date))
    news_items = edition.edition_news(token, team_name, start, end, run_date, match_blocks)

    return matches_data, transfers_data, news_items


def load_data_blocks(team_name: str, start: datetime, end: datetime, run_date: datetime):
    """The code-rendered 순위 / 다음 경기 / 결장 blocks, why any was left out,
    and the injured players' names (the news call is told not to restate them)."""
    token = team_name.replace(" ", "_")
    overview = edition.load_overview(token, start, end, run_date)
    fixtures = edition.load_fixtures(token, start, run_date)
    markdown, info = blocks.render(overview, fixtures, end, team_name)
    injured = [p["name"] for p in (overview or {}).get("injuries") or [] if p.get("name")]
    return markdown, info, injured


def edition_inputs(team_name: str, run_date: datetime, news_items, block_info: dict, injured,
                   summarizer) -> dict:
    """What the model was given and what code added: the evaluation scores an
    edition against this (evaluate/utils.load_inputs), not against a fresh
    read of datas/, so later changes to edition.py can't move old scores."""
    return {
        "version": 1,
        "team": team_name,
        "date": run_date.strftime("%Y%m%d"),
        "news": [
            {"tag": f"N{i}", "headline": item.headline, "link": item.link,
             "published": item.published.strftime("%Y-%m-%d %H:%M") if item.published else None,
             "collected": item.collected.strftime("%Y-%m-%d"), "summary": item.summary}
            for i, item in enumerate(news_items, 1)
        ],
        "shown_separately": list(injured),
        "blocks": block_info,
        "tidied": summarizer.tidied,
        "raw": summarizer.raw,
    }


def generate_edition(team_name: str, run_date: datetime, summarizer=llmSummarizer) -> Tuple[str, dict]:
    """One team's newsletter for the edition of `run_date`, and its inputs
    record. The LLM calls it made are left in summarizer.calls
    (evaluate/harness.py reuses this with other models and prompts)."""
    start, end = edition.edition_window(run_date)
    matches_data, transfers_data, news_items = load_weekly_data(team_name, start, end, run_date)
    data_blocks, block_info, injured = load_data_blocks(team_name, start, end, run_date)
    summarizer.calls = []
    body = summarizer.generate_newsletter(matches_data, transfers_data, news_items, data_blocks, injured)
    markdown = f"# {team_name} · 주간 뉴스레터 ({edition.date_range_label(start, end)})\n\n" + body
    return markdown, edition_inputs(team_name, run_date, news_items, block_info, injured, summarizer)


def write_edition(folder, team_name: str, markdown: str, inputs: dict) -> str:
    """newsletter_{team}.md, plus inputs/{team}.json beside it."""
    folder = Path(folder)
    token = team_name.replace(" ", "_")
    (folder / "inputs").mkdir(parents=True, exist_ok=True)
    path = folder / f"newsletter_{token}.md"
    path.write_text(markdown, encoding="utf-8")
    (folder / "inputs" / f"{token}.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=1), encoding="utf-8")
    return str(path)


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
        newsletter, inputs = generate_edition(team_name, run_date)
        output_path = write_edition(folder, team_name, newsletter, inputs)
        usage_by_team[team_name] = llmSummarizer.calls

        print(f"Generated: {output_path}")

    if usage_by_team:
        write_usage(folder, llmSummarizer.model, usage_by_team)
