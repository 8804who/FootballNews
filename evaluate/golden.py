#!/usr/bin/env python3
"""
golden.py — freeze a real edition and its sources as a regression case.

Every defect the evaluation must catch becomes a case in tests/golden/: the
newsletter text, the source files of its week, and what the evaluator has to
find. tests/test_golden.py replays them all, so a metric change that stops
catching a known problem fails the tests (CI runs them on every push).

    python evaluate/golden.py --name chelsea_20260831_reversed_result \
        --date 20260831 --team Chelsea \
        --why "Chelsea won 3-2 at Fulham; the edition printed 'Chelsea vs Fulham 2-3'"

Then write the case's "expect" block by hand (see the existing cases). Keys:
  hold (bool), problems / warnings (substrings that must appear in the gate's
  findings), metric_min / metric_max ({metric: bound}), facts_failed
  (substrings of failed match-fact claims). Add --also for other clubs whose
  sources a check needs (the "only in another club's sources" check).
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running from the project root: python evaluate/golden.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import edition
from evaluate.utils import BASE_DIR, DATA_ROOT, NEWSLETTER_ROOT, parse_date

GOLDEN_DIR = BASE_DIR / "tests" / "golden"


def source_files(token: str, date_str: str) -> dict:
    """{path relative to datas/: text} for one club's edition week."""
    date = parse_date(date_str)
    start, _ = edition.edition_window(date)
    files = {}
    for d in edition.folder_dates(start, date):
        for rel in (f"fotmob/{d}/team_daily_report_{token}_matches.md",
                    f"fotmob/{d}/team_daily_report_{token}_transfers.md",
                    f"fotmob/{d}/team_daily_report_{token}_fixtures.json",
                    f"news_rss/{d}/team_daily_report_{token}.md"):
            if (DATA_ROOT / rel).exists():
                files[rel] = (DATA_ROOT / rel).read_text(encoding="utf-8")
    return files


def capture(name: str, date_str: str, team: str, why: str, also=()) -> Path:
    token = team.replace(" ", "_")
    newsletter = f"newsletter/{date_str}/newsletter_{token}.md"
    files = {newsletter: (NEWSLETTER_ROOT / date_str / f"newsletter_{token}.md").read_text(encoding="utf-8")}
    for club in (token, *[a.replace(" ", "_") for a in also]):
        files.update(source_files(club, date_str))
    case = {"name": name, "date": date_str, "team": team, "also": list(also), "why": why, "expect": {}, "files": files}
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = GOLDEN_DIR / f"{name}.json"
    path.write_text(json.dumps(case, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Freeze an edition + its sources as a golden test case.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--date", required=True, help="Newsletter folder date (YYYYMMDD)")
    parser.add_argument("--team", required=True)
    parser.add_argument("--why", required=True, help="What's wrong (or right) with this edition")
    parser.add_argument("--also", default="", help="Comma-separated other clubs whose sources are needed")
    args = parser.parse_args()
    print(capture(args.name, args.date, args.team, args.why, [a for a in args.also.split(",") if a]))
