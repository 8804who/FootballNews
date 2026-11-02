"""Which matches and headlines belong to a weekly edition.

collect_news.py writes one folder per day it *runs*, and each run looks a few
days back, so the same match lands in several folders and a folder's date is
not a match date. An edition is therefore built from kickoff and publish
times: it covers the week before its Monday (Monday 00:00 UTC to the next
Monday 00:00 UTC), and every match that kicked off in that week is included
exactly once, whichever folder it was found in. The previous edition's
Sunday is never repeated, and a match missed by a failed run is picked up
from the next run's folder.

generate_newsletter.py, evaluate/ and send_mail.py all use this module, so
the model, the evaluator and the email subject agree on what "this week" is.
"""

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from team_names import aliases, distinctive_words, fold, normalize

DATA_ROOT = Path(__file__).resolve().parent / "datas"

_MATCH_HEADER_RE = re.compile(r"^## .*?Match: (?:vs|@) (.+)$", re.MULTILINE)
_KICKOFF_RE = re.compile(r"^- \*\*Date:\*\* (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", re.MULTILINE)
_VENUE_RE = re.compile(r"^- \*\*Venue:\*\* (Home|Away)", re.MULTILINE)
_SCORE_LINE_RE = re.compile(r"^- \*\*Score:\*\* (\d+)\s*-\s*(\d+)[ \t]*$", re.MULTILINE)
_TRANSFER_DATE_RE = re.compile(r"\*\*Date:\*\* (\d{4}-\d{2}-\d{2})")
# "- [2026-10-20 07:00] Headline - Outlet (https://…)"; files written before
# collect_news stored publish times have no "[…]" prefix.
_NEWS_LINE_RE = re.compile(
    r"^- (?:\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] )?(.+) \((https?://[^)\s]+)\)\s*$"
)
_GOSSIP_RE = re.compile(r"paper talk|gossip|rumou?rs?\b", re.IGNORECASE)

# Google News answers a club search with section and landing pages too. They
# name the club but carry no story, and the model turns them into invented
# rumors ("a BBC transfer page suggests reinforcements — 50%").
_INDEX_PAGE_RES = [re.compile(p, re.IGNORECASE) for p in (
    r"transfer news, results, fixtures",
    r"scores (?:&|and) fixtures",
    r"transfer news,? rumou?rs,? and gossip",
    r"\blive updates\b",
    r"\blive!(?=\s)",          # "Arsenal vs Everton LIVE! … score updates"
    r"\bscore updates\b",
    r"^football gossip\b",
    r"^football games, results, scores",
)]


# ─────────────────────────── the edition week ───────────────────────────────

def _utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)


def edition_window(run_date: datetime) -> Tuple[datetime, datetime]:
    """(start, end) for an edition generated on `run_date`: the 7 days before
    that week's Monday, in UTC. Any run from Monday to Sunday gets the same
    window, so a Tuesday re-run reproduces Monday's edition."""
    day = _utc(run_date).date()
    monday = day - timedelta(days=day.weekday())
    end = datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)
    return end - timedelta(days=7), end


def date_range_label(start: datetime, end: datetime) -> str:
    """'2026-10-19 ~ 2026-10-25' — the days an edition covers."""
    return f"{start:%Y-%m-%d} ~ {end - timedelta(days=1):%Y-%m-%d}"


def folder_dates(start: datetime, run_date: datetime) -> List[str]:
    """Collection folders (YYYYMMDD) that can hold this edition's data: a match
    is collected the day after it's played, or a few days later if a run
    failed, so from the week's first day through the run day."""
    first, last = start.date(), _utc(run_date).date()
    return [(first + timedelta(days=i)).strftime("%Y%m%d") for i in range((last - first).days + 1)]


# ─────────────────────────── matches ────────────────────────────────────────

def split_match_blocks(text: str) -> List[str]:
    """The '## 🏟️ Match: vs …' sections of a collect_news matches file."""
    starts = [m.start() for m in _MATCH_HEADER_RE.finditer(text)]
    return [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]


def match_kickoff(block: str) -> Optional[datetime]:
    m = _KICKOFF_RE.search(block)
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc) if m else None


def match_opponent(block: str) -> str:
    m = _MATCH_HEADER_RE.search(block)
    return m.group(1).strip() if m else ""


def load_matches(token: str, start: datetime, end: datetime, run_date: datetime,
                 root: Path = DATA_ROOT) -> List[str]:
    """Match blocks that kicked off in [start, end), oldest first, each once.
    A match collected on several days keeps its latest copy, since later runs
    see FotMob's final events and stats."""
    found = {}
    for d in folder_dates(start, run_date):
        path = root / "fotmob" / d / f"team_daily_report_{token}_matches.md"
        if not path.exists():
            continue
        for block in split_match_blocks(path.read_text(encoding="utf-8")):
            kickoff = match_kickoff(block)
            if kickoff and start <= kickoff < end:
                found[(kickoff, match_opponent(block))] = block
    return [found[k] for k in sorted(found)]


def shootout(block: str, fixtures: Optional[List[dict]]) -> Optional[str]:
    """'Fleetwood won 5-3 on penalties' when FotMob's fixture list says this
    match went to penalties (fixture lists saved from Oct 31 2026 on). The
    match report itself only has the 1-1, which reads as a draw: Arsenal's
    cup exit to Fleetwood would have gone out as '1-1로 비겼습니다'."""
    kickoff, score = match_kickoff(block), match_score(block)
    if not (kickoff and score and fixtures):
        return None
    for f in fixtures:
        if fixture_kickoff(f) != kickoff or f.get("decided") != "After penalties":
            continue
        try:
            home_pens, away_pens = int(f["home_total"]) - score[0], int(f["away_total"]) - score[1]
        except (KeyError, TypeError, ValueError):
            return None
        if home_pens == away_pens:
            return None
        winner = f.get("home") if home_pens > away_pens else f.get("away")
        return f"{winner} won {max(home_pens, away_pens)}-{min(home_pens, away_pens)} on penalties"
    return None


def with_result_line(block: str, team_name: str) -> str:
    """Add "- **Result:** Fulham 2 - 3 Chelsea (Chelsea won)" after the score.

    The score is always home-away, and models misread it for away games:
    "Venue: Away, Score: 2 - 3" came out as a 2-3 defeat in a sent edition
    (Chelsea at Fulham, Aug 31), and the evaluation's own judge model made
    the same mistake. Spelling out who won removes the guesswork.
    """
    venue, score, opponent = _VENUE_RE.search(block), _SCORE_LINE_RE.search(block), match_opponent(block)
    if not (venue and score and opponent):
        return block
    home_goals, away_goals = int(score.group(1)), int(score.group(2))
    at_home = venue.group(1) == "Home"
    home, away = (team_name, opponent) if at_home else (opponent, team_name)
    ours, theirs = (home_goals, away_goals) if at_home else (away_goals, home_goals)
    outcome = "won" if ours > theirs else "lost" if ours < theirs else "drew"
    line = f"\n- **Result:** {home} {home_goals} - {away_goals} {away} ({team_name} {outcome})"
    return block[:score.end()] + line + block[score.end():]


def matches_markdown(team_name: str, blocks: Sequence[str], start: datetime, end: datetime,
                     fixtures: Optional[List[dict]] = None) -> str:
    """Selected blocks under the header collect_news.py writes ('' if none),
    each with an explicit result line (and the shootout, when `fixtures`
    shows one)."""
    if not blocks:
        return ""
    header = f"# 📅 Weekly Report: {team_name}\n**Period:** {date_range_label(start, end)}\n\n---\n\n"
    blocks = [_with_shootout(with_result_line(b, team_name), shootout(b, fixtures)) for b in blocks]
    return header + "".join(b if b.endswith("\n") else b + "\n" for b in blocks)


def _with_shootout(block: str, note: Optional[str]) -> str:
    if not note:
        return block
    return re.sub(r"(^- \*\*Result:\*\* .*?)\)$", rf"\1; {note})", block, count=1, flags=re.MULTILINE)


def played_matches(blocks: Sequence[str]) -> List[Tuple[datetime, str]]:
    """(kickoff, opponent) for each selected match."""
    return [(match_kickoff(b), match_opponent(b)) for b in blocks]


def load_fixtures(token: str, start: datetime, run_date: datetime,
                  root: Path = DATA_ROOT) -> Optional[List[dict]]:
    """FotMob's full fixture list from the newest collection folder that has
    one (collect_news.py started saving it in Oct 2026), or None."""
    for d in reversed(folder_dates(start, run_date)):
        path = root / "fotmob" / d / f"team_daily_report_{token}_fixtures.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def fixture_kickoff(fixture: dict) -> Optional[datetime]:
    try:
        return datetime.strptime(fixture.get("utc_time") or "", "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def uncollected_fixtures(fixtures: Optional[List[dict]], blocks: Sequence[str],
                         start: datetime, end: datetime) -> Tuple[int, List[dict]]:
    """(finished fixtures this week per FotMob's list, the ones with no
    collected match). A newsletter can be faithful to its source and still
    miss the weekend if collection failed; this is how that shows."""
    if not fixtures:
        return 0, []
    collected = {match_kickoff(b) for b in blocks}
    finished = [f for f in fixtures
                if f.get("finished") and not f.get("cancelled")
                and (k := fixture_kickoff(f)) and start <= k < end]
    return len(finished), [f for f in finished if fixture_kickoff(f) not in collected]


# ─────────────────────────── transfers ──────────────────────────────────────

def load_transfers(token: str, start: datetime, end: datetime, run_date: datetime,
                   root: Path = DATA_ROOT) -> List[str]:
    """FotMob transfer lines dated in [start, end), each once."""
    seen, lines = set(), []
    for d in folder_dates(start, run_date):
        path = root / "fotmob" / d / f"team_daily_report_{token}_transfers.md"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _TRANSFER_DATE_RE.search(line)
            if not (line.startswith("- ") and m) or line in seen:
                continue
            if start.date() <= datetime.strptime(m.group(1), "%Y-%m-%d").date() < end.date():
                seen.add(line)
                lines.append(line)
    return lines


def transfers_markdown(team_name: str, lines: Sequence[str]) -> str:
    return f"Team: {team_name}\nTransfers:\n" + "\n".join(lines) if lines else ""


# ─────────────────────────── headlines ──────────────────────────────────────

def _split_outlet(headline: str) -> Tuple[str, str]:
    """Google News titles end in " - Outlet"."""
    head, sep, tail = headline.rpartition(" - ")
    if sep and head and len(tail) <= 40:
        return head.strip(), tail.strip()
    return headline.strip(), ""


@dataclass(frozen=True)
class NewsItem:
    headline: str                  # as Google News gives it: "Story - Outlet"
    link: str
    published: Optional[datetime]  # None for lines collected before publish times were stored
    collected: date                # the folder it was read from
    summary: str = ""              # BBC's one-line standfirst; Google News gives none

    @property
    def title(self) -> str:
        return _split_outlet(self.headline)[0]

    @property
    def source_text(self) -> str:
        """Everything the model was told about this story: what an item
        written from it may say, and what the evaluation checks it against."""
        return f"{self.headline}\n{self.summary}" if self.summary else self.headline

    @property
    def outlet(self) -> str:
        return _split_outlet(self.headline)[1]

    @property
    def kind(self) -> str:
        """'가십' for round-ups of other papers (Sky's Paper Talk, gossip columns), else '보도'."""
        return "가십" if _GOSSIP_RE.search(self.headline) else "보도"


def parse_news_line(line: str, collected: date) -> Optional[NewsItem]:
    m = _NEWS_LINE_RE.match(line.strip())
    if not m:
        return None
    published = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc) if m.group(1) else None
    return NewsItem(headline=m.group(2).strip(), link=m.group(3), published=published, collected=collected)


def is_index_page(headline: str, team_aliases: Iterable[str] = ()) -> bool:
    """A club section/landing page ("Man City - BBC", "… Transfer news,
    results, fixtures") rather than a story."""
    if any(r.search(headline) for r in _INDEX_PAGE_RES):
        return True
    title, _ = _split_outlet(headline)
    return normalize(title) in {normalize(a) for a in team_aliases}


def _mentions(text: str, team: str) -> bool:
    folded = fold(text)
    for word in {fold(team), *distinctive_words(team)}:
        if word and re.search(rf"(?<![^\W\d_]){re.escape(word)}(?![^\W\d_])", folded):
            return True
    return False


def _is_stale_preview(item: NewsItem, played: Sequence[Tuple[datetime, str]]) -> bool:
    """Published before a match it mentions, and that match has been played."""
    if item.published is None:
        return False
    return any(kickoff and item.published < kickoff and _mentions(item.headline, opponent)
               for kickoff, opponent in played)


def load_news(token: str, team_name: str, start: datetime, end: datetime, run_date: datetime,
              played: Sequence[Tuple[datetime, str]] = (), root: Path = DATA_ROOT) -> List[NewsItem]:
    """Headlines for the edition, oldest first, each once.

    Kept when published in [start, end). Lines without a publish time fall
    back to their folder date, counting folders after the week's first day
    (an item is collected within a day or so of publishing, so last Monday's
    folder is mostly the previous week's news).

    Dropped: club index pages, and pieces about an upcoming match that has
    since been played — "X is a doubt for Saturday" next to Saturday's result
    would read as current news.
    """
    team_aliases = aliases(team_name)
    seen, items = set(), []
    for d in folder_dates(start, run_date):
        path = root / "news_rss" / d / f"team_daily_report_{token}.md"
        if not path.exists():
            continue
        collected = datetime.strptime(d, "%Y%m%d").date()
        for line in path.read_text(encoding="utf-8").splitlines():
            item = parse_news_line(line, collected)
            if item is None or normalize(item.title) in seen:
                continue
            if item.published:
                in_week = start <= item.published < end
            else:
                in_week = start.date() < collected <= end.date()
            if not in_week or is_index_page(item.headline, team_aliases) or _is_stale_preview(item, played):
                continue
            seen.add(normalize(item.title))
            items.append(item)
    return sorted(items, key=_news_order)


def _news_order(item: NewsItem) -> datetime:
    return item.published or datetime.combine(item.collected, datetime.min.time(), timezone.utc)


def load_bbc_news(token: str, team_name: str, start: datetime, end: datetime, run_date: datetime,
                  played: Sequence[Tuple[datetime, str]] = (), root: Path = DATA_ROOT) -> List[NewsItem]:
    """Stories from BBC Sport's club feed (collect_news.py, from Nov 2026)
    published in [start, end), each once, with their summaries."""
    team_aliases = aliases(team_name)
    seen, items = set(), []
    for d in folder_dates(start, run_date):
        path = root / "news_rss" / d / f"team_daily_report_{token}_bbc.json"
        if not path.exists():
            continue
        collected = datetime.strptime(d, "%Y%m%d").date()
        for raw in json.loads(path.read_text(encoding="utf-8")):
            try:
                published = datetime.strptime(raw["published"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            item = NewsItem(headline=f"{raw.get('title', '').strip()} - BBC", link=raw.get("link", ""),
                            published=published, collected=collected, summary=(raw.get("summary") or "").strip())
            key = normalize(item.title)
            if not item.title or not item.link or key in seen or not start <= published < end:
                continue
            if is_index_page(item.headline, team_aliases) or _is_stale_preview(item, played):
                continue
            seen.add(key)
            items.append(item)
    return sorted(items, key=_news_order)


def match_score(block: str) -> Optional[Tuple[int, int]]:
    """(home goals, away goals) of a collected match block."""
    m = _SCORE_LINE_RE.search(block)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _is_match_report(item: NewsItem, blocks: Sequence[str]) -> bool:
    """A report of a match that's already on this edition's scoreboard:
    "Arsenal 2-0 Everton: Konsa and Gabriel …", published after kickoff.
    Requiring that match's own final score keeps "out for 2-3 weeks" and
    "4-3-3" stories."""
    if item.published is None:
        return False
    for block in blocks:
        kickoff, score, opponent = match_kickoff(block), match_score(block), match_opponent(block)
        if not (kickoff and score and opponent) or item.published < kickoff:
            continue
        a, b = score
        if re.search(rf"(?<!\d)(?:{a}\s*[-–]\s*{b}|{b}\s*[-–]\s*{a})(?!\d)", item.title) and _mentions(item.title, opponent):
            return True
    return False


def edition_news(token: str, team_name: str, start: datetime, end: datetime, run_date: datetime,
                 blocks: Sequence[str] = (), root: Path = DATA_ROOT) -> List[NewsItem]:
    """The stories an edition is generated from: BBC's club feed merged with
    Google News, minus match reports already on the scoreboard.

    BBC wins a duplicate because it carries the summary. Google's titles for
    BBC stories often differ from BBC's own, so on a day the BBC feed gave
    stories, Google's BBC items are dropped instead of matched.

    Only generation uses this; the evaluation reads what was actually used
    from inputs/{team}.json, and editions from before it existed keep being
    scored against load_news alone, so their scores don't move.
    """
    played = played_matches(blocks)
    bbc = load_bbc_news(token, team_name, start, end, run_date, played, root)
    bbc_days = {item.collected for item in bbc}
    seen = {normalize(item.title) for item in bbc}
    merged = list(bbc)
    for item in load_news(token, team_name, start, end, run_date, played, root):
        if normalize(item.title) in seen:
            continue
        if item.outlet.startswith("BBC") and item.collected in bbc_days:
            continue
        merged.append(item)
    return sorted((i for i in merged if not _is_match_report(i, blocks)), key=_news_order)


# ─────────────────────────── table and injuries ─────────────────────────────

def load_overview(token: str, start: datetime, end: datetime, run_date: datetime,
                  root: Path = DATA_ROOT) -> Optional[dict]:
    """The newest FotMob table/injury snapshot collected at or after the
    edition's end, or None. An older one (Monday's collection failed, so
    Sunday's is the newest) predates the weekend's matches: its table and
    injuries would contradict the scoreboard in the same email."""
    for d in reversed(folder_dates(start, run_date)):
        path = root / "fotmob" / d / f"team_daily_report_{token}_overview.json"
        if not path.exists():
            continue
        overview = json.loads(path.read_text(encoding="utf-8"))
        try:
            collected = datetime.strptime(overview.get("collected_at") or "", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        return overview if collected >= end else None
    return None
