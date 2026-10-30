"""Shared paths, regex helpers, and data-loading utilities for all evaluators."""

import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple

import edition

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_ROOT = BASE_DIR / "datas"
NEWSLETTER_ROOT = DATA_ROOT / "newsletter"

SCORE_RE = re.compile(r"(\d+)\s*-\s*(\d+)")

# "Red Card" can appear with a parenthetical qualifier, e.g.
# "Red Card (Second Yellow Card): {player}" — allow that optional "(...)"
# between the label and the colon.
_EVENT_RE = re.compile(
    r'(?:Goal|Red Card(?:\s*\([^)]*\))?|Yellow Card|Player Substitution):\s*'
    r'([A-Z][^\(\n\|]*)'
)
# The stats table header names both sides the way FotMob shortens them
# ("| Stat | Como | Man United |"), which is how the model writes them.
_STATS_HEADER_RE = re.compile(r"^\| Stat \| (.+?) \| (.+?) \|$", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
_URL_RE = re.compile(r"https?://\S+")


def parse_date(name: str) -> Optional[datetime]:
    try:
        return datetime.strptime(name, "%Y%m%d")
    except ValueError:
        return None


def strip_links(text: str) -> str:
    """'[BBC](https://…)' → 'BBC', bare URLs removed — so link targets aren't
    read as names or English text by the metrics."""
    return _URL_RE.sub("", _MD_LINK_RE.sub(r"\1", text))


def extract_links(text: str) -> List[Tuple[str, str]]:
    """(label, url) for every markdown link in the text."""
    return _MD_LINK_RE.findall(text)


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


def source_available(token: str, newsletter_date: datetime) -> bool:
    """Whether any collected data for this team exists in the edition's
    folders. Without it nothing can be measured (e.g. a partial download),
    which is different from a week that genuinely had no matches or news."""
    start, _ = edition.edition_window(newsletter_date)
    for d in edition.folder_dates(start, newsletter_date):
        for path in (DATA_ROOT / "fotmob" / d / f"team_daily_report_{token}_matches.md",
                     DATA_ROOT / "news_rss" / d / f"team_daily_report_{token}.md"):
            if path.exists():
                return True
    return False


def load_match_blocks(token: str, newsletter_date: datetime) -> List[str]:
    """The match blocks generate_newsletter.py gave the model for this edition
    (edition.load_matches: kicked off in the edition week, each once)."""
    start, end = edition.edition_window(newsletter_date)
    return edition.load_matches(token, start, end, newsletter_date, root=DATA_ROOT)


def load_transfer_lines(token: str, newsletter_date: datetime) -> List[str]:
    start, end = edition.edition_window(newsletter_date)
    return edition.load_transfers(token, start, end, newsletter_date, root=DATA_ROOT)


def load_fotmob_for_team(
    token: str,
    newsletter_date: datetime,
) -> Tuple[List[Tuple[str, str, int, int]], Set[str]]:
    """Matches + player names for the edition dated `newsletter_date`.

    Uses the same selection generate_newsletter.py gives the model
    (edition.load_matches): every match that kicked off in the edition week,
    once, wherever collect_news.py happened to store it.
    """
    start, end = edition.edition_window(newsletter_date)
    blocks = load_match_blocks(token, newsletter_date)
    text = edition.matches_markdown(token.replace("_", " "), blocks, start, end)

    matches = _parse_fotmob_matches(text)
    players = _parse_source_players(text)
    # Team names (home/away) are legitimate proper nouns too — fold them into
    # the known-names pool so hallucination detection doesn't flag
    # correctly-used team names.
    for home, away, _, _ in matches:
        players.add(home)
        players.add(away)
    for pair in _STATS_HEADER_RE.findall(text):
        players.update(pair)
    return matches, players


def resolve_newsletter_token(stem: str) -> Optional[str]:
    """Extract the team token from a newsletter filename stem.

    Real newsletter files are named "newsletter_{Team_Name}.md" by
    generate_newsletter.py.
    """
    prefix = "newsletter_"
    if stem.startswith(prefix):
        return stem[len(prefix):]
    return None


def load_news_items_for_team(token: str, newsletter_date: datetime) -> List["edition.NewsItem"]:
    """The headlines generate_newsletter.py gave the model for this edition."""
    start, end = edition.edition_window(newsletter_date)
    blocks = edition.load_matches(token, start, end, newsletter_date, root=DATA_ROOT)
    return edition.load_news(
        token, token.replace("_", " "), start, end, newsletter_date,
        edition.played_matches(blocks), root=DATA_ROOT,
    )


def load_news_source_for_team(token: str, newsletter_date: datetime) -> str:
    """Headlines + FotMob transfer lines the model saw for this edition, as
    plain text (URLs left out so opaque Google News IDs don't pollute the
    word pool)."""
    headlines = [item.headline for item in load_news_items_for_team(token, newsletter_date)]
    return "\n".join(headlines + load_transfer_lines(token, newsletter_date))
