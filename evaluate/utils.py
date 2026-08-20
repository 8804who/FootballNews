"""Shared paths, regex helpers, and data-loading utilities for all evaluators."""

import re
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
FOTMOB_ROOT = BASE_DIR / "datas" / "fotmob"
NEWSLETTER_ROOT = BASE_DIR / "datas" / "newsletter"

SCORE_RE = re.compile(r"(\d+)\s*-\s*(\d+)")

# "Red Card" can appear with a parenthetical qualifier, e.g.
# "Red Card (Second Yellow Card): {player}" — allow that optional "(...)"
# between the label and the colon.
_EVENT_RE = re.compile(
    r'(?:Goal|Red Card(?:\s*\([^)]*\))?|Yellow Card|Player Substitution):\s*'
    r'([A-Z][^\(\n\|]*)'
)


def parse_date(name: str) -> Optional[datetime]:
    try:
        return datetime.strptime(name, "%Y%m%d")
    except ValueError:
        return None


def _parse_fotmob_matches(text: str) -> List[Tuple[str, str, int, int]]:
    """Return (home_team, away_team, home_goals, away_goals) from fotmob file text.

    Score format in fotmob files is always Home-Away regardless of which team
    is the 'main' team being tracked. Each match is its own '...Match: ...'
    block, so blocks can be parsed independently with no shared state (and no
    risk of a partial record's venue/score leaking into the next block).
    """
    m = re.search(r"Weekly Report:\s*(.+)", text)
    main_team = m.group(1).strip() if m else None
    if not main_team:
        return []

    results: List[Tuple[str, str, int, int]] = []
    for block in text.split("Match:")[1:]:
        block_lines = block.splitlines()
        om = re.search(r"\s*(?:vs|@)\s*(.+)", block_lines[0])
        venue = score = None
        for line in block_lines[1:]:
            if venue is None and "Venue:" in line:
                vm = re.search(r"Venue:\s*(.+)", line)
                venue = vm.group(1).strip() if vm else None
            elif score is None and "Score:" in line:
                sm = SCORE_RE.search(line)
                score = (int(sm.group(1)), int(sm.group(2))) if sm else None
            if venue and score:
                break
        if not (om and venue and score):
            continue
        opponent = om.group(1).strip()
        tg, og = score
        if "Home" in venue:
            results.append((main_team, opponent, tg, og))
        else:
            # main_team is Away → tg is Home (opponent) goals
            results.append((opponent, main_team, tg, og))
    return results


def extract_newsletter_matches(text: str) -> List[Tuple[str, str, int, int]]:
    """Extract (home, away, home_goals, away_goals) from a newsletter scoreboard table."""
    results = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if re.match(r"^\|\s*[-:]+", s):
            continue
        cells = [c.strip() for c in s.split("|")[1:-1]]
        if len(cells) < 2 or not re.search(r"\svs\s", cells[0], re.IGNORECASE):
            continue
        vm = re.search(r"(.+?)\s+vs\s+(.+)", cells[0], re.IGNORECASE)
        if not vm:
            continue
        home = re.sub(r"\s*\([^)]*\)", "", vm.group(1)).strip()
        away = re.sub(r"\s*\([^)]*\)", "", vm.group(2)).strip()
        sm = SCORE_RE.search(cells[1])
        if not sm:
            continue
        if home and away:
            results.append((home, away, int(sm.group(1)), int(sm.group(2))))
    return results


def _parse_source_players(text: str) -> Set[str]:
    """All player names referenced in fotmob file text."""
    names: Set[str] = set()

    for m in _EVENT_RE.finditer(text):
        for part in re.split(r'\s*->\s*', m.group(1).strip()):
            part = part.strip()
            if part:
                names.add(part)

    for m in re.finditer(r'assist by\s+([A-Z][^\)\n]+)', text):
        raw = m.group(1).strip()
        if raw not in ("Own goal", "Penalty", "None"):
            names.add(raw)

    return names


@lru_cache(maxsize=None)
def _load_fotmob_file(path: Path) -> Tuple[Tuple[Tuple[str, str, int, int], ...], frozenset]:
    """Read + parse a fotmob file once. Cached because the same file falls inside
    the lookback window of multiple (weekly, overlapping) newsletters."""
    text = path.read_text(encoding="utf-8")
    return tuple(_parse_fotmob_matches(text)), frozenset(_parse_source_players(text))


def extract_fotmob_matches(path: Path) -> List[Tuple[str, str, int, int]]:
    matches, _ = _load_fotmob_file(path)
    return list(matches)


def extract_source_players(path: Path) -> Set[str]:
    _, players = _load_fotmob_file(path)
    return set(players)


def load_fotmob_for_team(
    token: str,
    newsletter_date: datetime,
) -> Tuple[List[Tuple[str, str, int, int]], Set[str]]:
    """Aggregate fotmob matches + player names from the 8 days up to and
    including the newsletter date.

    Mirrors generate_newsletter.py's load_weekly_data() window exactly: 7
    days before the newsletter date *plus* the newsletter's own generation
    day. The generation day is included because collect_news.py names its
    output folder by the day it runs, not the match date — so a Sunday-night
    UK match (Monday dawn in Korea) lands in that same-day folder, and the
    LLM does see it. Matches are deduplicated because each day's snapshot
    file is itself a rolling report and can repeat matches already seen on a
    previous day within the window.
    """
    matches: Set[Tuple[str, str, int, int]] = set()
    players: Set[str] = set()
    for delta in range(0, 8):
        d_str = (newsletter_date - timedelta(days=delta)).strftime("%Y%m%d")
        f = FOTMOB_ROOT / d_str / f"team_daily_report_{token}_matches.md"
        if f.exists():
            m, p = _load_fotmob_file(f)
            matches.update(m)
            players |= p

    # Team names (home/away) are legitimate proper nouns too — fold them into
    # the known-names pool so hallucination detection doesn't flag
    # correctly-used team names.
    for home, away, _, _ in matches:
        players.add(home)
        players.add(away)

    return list(matches), players


def resolve_newsletter_token(stem: str) -> Optional[str]:
    """Extract the team token from a newsletter filename stem.

    Real newsletter files are named "newsletter_{Team_Name}.md" by
    generate_newsletter.py.
    """
    prefix = "newsletter_"
    if stem.startswith(prefix):
        return stem[len(prefix):]
    return None
