#!/usr/bin/env python3
"""
gate.py — yes/no checks on each club's edition, reported on the dashboard.

The weighted metrics in evaluate_main.py follow quality over time. These are
yes/no checks that a correct edition always passes. They hold nothing:
every edition is sent, and a club that fails one is *flagged* — listed in
the step summary and on the dashboard so the operator can see what went
wrong:

  1. every match in this week's source is on the scoreboard, with its score
  2. the scoreboard has no match the source doesn't (a repeat or invented game)
  3. FotMob's fixture list has no finished match this week that wasn't collected
  4. no name from the few-shot examples (example.yml is all fictional)
  5. no name found only in *another* club's sources this week
  6. every source link points at one of this club's headlines this week

Softer findings (names in no source at all, news items without a source
link, a low Korean ratio) are recorded as warnings.

Writes datas/newsletter/{date}/gate.json, which generate_dashboard.py shows.

Usage
-----
    python evaluate/gate.py --date 20261102
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set

import yaml

# Allow running from the project root: python evaluate/gate.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import edition
from evaluate import hallucination, language_compliance, match_facts, news_grounding, score_accuracy
from evaluate import utils
from evaluate.utils import (
    BASE_DIR,
    extract_links,
    extract_newsletter_matches,
    load_fotmob_for_team,
    load_match_blocks,
    load_news_items_for_team,
    load_news_source_for_team,
    parse_date,
    resolve_newsletter_token,
    strip_links,
)

EXAMPLE_YML = BASE_DIR / "example.yml"

# Capitalised sequences, allowing all-caps words ("Example FC").
_EXAMPLE_NAME_RE = re.compile(r"(?<![A-Za-z])[A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*)+")


def _words(names) -> Set[str]:
    return {w.lower() for n in names for w in n.split()}


def _contains(text: str, name: str) -> bool:
    return re.search(rf"(?<![A-Za-z]){re.escape(name.lower())}(?![A-Za-z])", text.lower()) is not None


def example_names() -> Set[str]:
    """Names in example.yml's inputs and outputs — all fictional, so one
    showing up in an edition means the model copied a few-shot example."""
    data = yaml.safe_load(EXAMPLE_YML.read_text(encoding="utf-8"))
    text = "\n".join(f"{ex['input']}\n{ex['output']}" for examples in data.values() for ex in examples)
    labels = {"Team", "Venue", "Match", "Score", "Key", "Events", "Official", "Transfers",
              "News", "Rumors", "Player", "Type", "Date", "Sky", "Sports", "BBC", "Paper", "Talk"}
    return {n for n in _EXAMPLE_NAME_RE.findall(text) if not set(n.split()) & labels}


def club_sources(token: str, date: datetime) -> Dict:
    """Everything this club's edition was generated from."""
    start, end = edition.edition_window(date)
    blocks = load_match_blocks(token, date)
    matches, players = load_fotmob_for_team(token, date)
    news_text = load_news_source_for_team(token, date)
    items = load_news_items_for_team(token, date)
    names = players | hallucination.extract_names(news_text)
    return {
        "start": start,
        "end": end,
        "blocks": blocks,
        "matches": matches,
        "text": edition.matches_markdown(token.replace("_", " "), blocks, start, end) + "\n" + news_text,
        "words": _words(names) | news_grounding.build_source_words(news_text, players),
        "links": {item.link for item in items},
        "fixtures": edition.load_fixtures(token, start, date, root=utils.DATA_ROOT),
    }


def _uncollected_fixtures(src: Dict) -> List[str]:
    """Finished fixtures this week (per FotMob's list) with no collected match."""
    _, missing = edition.uncollected_fixtures(src["fixtures"], src["blocks"], src["start"], src["end"])
    return [f"FotMob lists {f.get('home')} {f.get('score')} {f.get('away')} ({f.get('tournament')}, "
            f"{edition.fixture_kickoff(f):%Y-%m-%d %H:%M} UTC), but it was never collected" for f in missing]


def _unlinked_items(text: str) -> int:
    """Items under 루머 밀 / 드라마 앵글 that carry no source link (공식 뉴스
    items come from FotMob's transfer list, which has no link to give)."""
    section = news_grounding.extract_news_section(text)
    parts = re.split(r"^### (.*)$", section, flags=re.MULTILINE)
    count = 0
    for heading, body in zip(parts[1::2], parts[2::2]):
        if "루머" not in heading and "드라마" not in heading:
            continue
        items = re.split(r"\n(?=- )|\n\s*\n", body.strip())
        count += sum(1 for item in items if item.strip() and "](http" not in item)
    return count


def check_edition(token: str, date: datetime, text: str, all_sources: Dict[str, Dict]) -> Dict:
    src = all_sources[token]
    plain = strip_links(text)
    problems: List[str] = []
    warnings: List[str] = []

    # 1–2. Scoreboard vs. this week's source matches
    board = score_accuracy.compare_scoreboard(src["matches"], extract_newsletter_matches(plain))
    for m, row in board["wrong"]:
        problems.append(f"wrong score: {m[0]} vs {m[1]} ended {m[2]}-{m[3]}, "
                        f"the scoreboard has {row[0]} vs {row[1]} {row[2]}-{row[3]}")
    for m in board["missing"]:
        problems.append(f"missing from the scoreboard: {m[0]} vs {m[1]} {m[2]}-{m[3]}")
    for row in board["extra"]:
        problems.append(f"not in this week's source (repeat or invented): {row[0]} vs {row[1]} {row[2]}-{row[3]}")

    # 3. Matches FotMob says were played but collection missed
    problems.extend(_uncollected_fixtures(src))

    # 4. Few-shot example leakage
    for name in sorted(example_names()):
        if _contains(plain, name) and not _contains(src["text"], name):
            problems.append(f"copied from the few-shot examples: {name}")

    # 5. Names that belong to another club's sources this week
    names = hallucination.extract_names(plain)
    untraceable = {n for n in names if not _words([n]) & src["words"]}
    for name in sorted(untraceable):
        owners = [t.replace("_", " ") for t, other in all_sources.items()
                  if t != token and _words([name]) <= other["words"]]
        if owners:
            problems.append(f"{name} isn't in this club's sources this week, only in {', '.join(owners)}'s "
                            "(another club's story, or a stale repeat)")
            untraceable.discard(name)

    # 6. Links must be to this club's collected headlines
    for label, url in extract_links(text):
        if url not in src["links"]:
            problems.append(f"source link not among this club's headlines this week: [{label}]({url[:60]}…)")

    # Warnings
    facts = match_facts.evaluate(plain, src["blocks"])
    if facts["failed"]:
        warnings.append("match facts not in this week's events: " + "; ".join(facts["failed"]))
    if untraceable:
        warnings.append(f"names found in no source this week: {', '.join(sorted(untraceable))}")
    unlinked = _unlinked_items(text)
    if unlinked:
        warnings.append(f"{unlinked} news item(s) without a source link")
    lang = language_compliance.evaluate(text)
    if not lang["passed"]:
        warnings.append(f"Korean ratio {lang['ratio']:.0%} (target {lang['target']:.0%})")

    return {"flagged": bool(problems), "problems": problems, "warnings": warnings}


def run_gate(date_str: str) -> Dict:
    date = parse_date(date_str)
    folder = utils.NEWSLETTER_ROOT / date_str
    files = sorted(folder.glob("newsletter_*.md")) if folder.exists() else []
    tokens = [resolve_newsletter_token(f.stem) for f in files]
    all_sources = {t: club_sources(t, date) for t in tokens}

    teams = {}
    for f, token in zip(files, tokens):
        teams[token.replace("_", " ")] = check_edition(token, date, f.read_text(encoding="utf-8"), all_sources)
    return {"date": date_str, "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "teams": teams}


def render_summary(result: Dict) -> str:
    flagged = [t for t, r in result["teams"].items() if r["flagged"]]
    lines = [f"# Edition checks — {result['date']}", ""]
    lines.append(f"**Flagged: {', '.join(flagged)}**" if flagged else "All editions passed.")
    lines.append("")
    for team, r in result["teams"].items():
        lines.append(f"## {'⛔' if r['flagged'] else '✅'} {team}")
        for p in r["problems"]:
            lines.append(f"- {p}")
        for w in r["warnings"]:
            lines.append(f"- ⚠ {w}")
        lines.append("")
    lines.append("Nothing is held: every edition is sent, and these results appear on the dashboard.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Check each edition and record the results for the dashboard.")
    parser.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y%m%d"),
                        help="Newsletter folder to check (YYYYMMDD); defaults to today (UTC)")
    args = parser.parse_args()

    result = run_gate(args.date)
    if not result["teams"]:
        print(f"No newsletters found in datas/newsletter/{args.date}")
        return

    out = utils.NEWSLETTER_ROOT / args.date / "gate.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = render_summary(result)
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(summary)


if __name__ == "__main__":
    main()
