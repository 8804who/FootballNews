"""The blocks a newsletter shows straight from FotMob data: where the club
stands, its next fixtures, and who's out.

They're rendered by code, not the LLM, so nothing in them can be invented,
and each one is left out (heading and all) when its data is missing or
older than the edition's matches. A table from before Sunday's game next to
Sunday's result would contradict the scoreboard in the same email.
"""

import re
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import newsletter_sections as sections
from edition import fixture_kickoff
from summarizers.korean import particle
from team_names import canonical, normalize

# Fixed offset: Korea has no daylight saving, and CI runners have no tzdata promise.
KST = timezone(timedelta(hours=9))
_WEEKDAYS = "월화수목금토일"

_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}
_PART = {"Early": ("초", 5), "Mid": ("중순", 15), "Late": ("말", 25)}
_POSITIONS = {
    "GK": "골키퍼", "CB": "센터백", "LB": "왼쪽 풀백", "RB": "오른쪽 풀백",
    "LWB": "왼쪽 윙백", "RWB": "오른쪽 윙백", "DM": "수비형 미드필더",
    "CM": "중앙 미드필더", "CAM": "공격형 미드필더", "LM": "왼쪽 미드필더",
    "RM": "오른쪽 미드필더", "LW": "왼쪽 윙어", "RW": "오른쪽 윙어",
    "ST": "스트라이커", "CF": "스트라이커",
}
_ROLES = {"Keeper": "골키퍼", "Defender": "수비수", "Midfielder": "미드필더", "Attacker": "공격수"}
MAX_INJURIES = 6


def _md(text) -> str:
    """FotMob text made safe for Markdown (and the table's cell borders)."""
    return re.sub(r"([\\`*_\[\]<>|#])", r"\\\1", str(text or "")).strip()


# ─────────────────────────── times ──────────────────────────────────────────

def _clock(hour: int, minute: int) -> str:
    # Midnight is "0시": "토요일 자정" and "일요일 0시" are the same moment,
    # and only the second matches the date written before it.
    if hour == 0:
        base = "0시"
    elif hour < 6:
        base = f"새벽 {hour}시"
    elif hour < 12:
        base = f"오전 {hour}시"
    elif hour == 12:
        base = "낮 12시"
    elif hour < 18:
        base = f"오후 {hour - 12}시"
    elif hour < 21:
        base = f"저녁 {hour - 12}시"
    else:
        base = f"밤 {hour - 12}시"
    return f"{base} {minute}분" if minute else base


def kst_label(moment: datetime, time_tbd: bool = False) -> str:
    """'11월 5일(목) 새벽 5시' for a UTC kickoff."""
    k = moment.astimezone(KST)
    day = f"{k.month}월 {k.day}일({_WEEKDAYS[k.weekday()]})"
    return f"{day} 시간 미정" if time_tbd else f"{day} {_clock(k.hour, k.minute)}"


# ─────────────────────────── standings ──────────────────────────────────────

def _name(row: dict) -> str:
    return _md(row.get("shortName") or row.get("name"))


def _own_row(rows: Sequence[dict], team_id, team_name: str) -> Optional[int]:
    for i, row in enumerate(rows):
        if team_id is not None and row.get("id") == team_id:
            return i
    for i, row in enumerate(rows):
        if canonical(row.get("name") or "") == team_name or canonical(row.get("shortName") or "") == team_name:
            return i
    return None


def _finished_league_fixtures(fixtures: Optional[List[dict]], league: dict, end: datetime) -> Optional[int]:
    """League matches FotMob's fixture list shows as finished before `end`."""
    if fixtures is None:
        return None
    league_id, league_name = league.get("league_id"), league.get("league_name")

    def in_league(f):
        if league_id is not None and f.get("tournament_id") is not None:
            return f["tournament_id"] == league_id
        return f.get("tournament") == league_name

    return sum(1 for f in fixtures
               if f.get("finished") and not f.get("cancelled") and in_league(f)
               and (k := fixture_kickoff(f)) and k < end)


def _goals_for(row: dict) -> int:
    m = re.match(r"(\d+)", str(row.get("scoresStr") or ""))
    return int(m.group(1)) if m else 0


def _tiebreak(a: dict, b: dict) -> str:
    if a.get("goalConDiff") != b.get("goalConDiff"):
        return "골득실"
    if _goals_for(a) != _goals_for(b):
        return "다득점"
    return "순위 규정"


def _with(row: dict) -> str:
    """'Man City와' / 'Arsenal과': the particle follows how the name is said."""
    name = row.get("shortName") or row.get("name") or ""
    return _md(name) + (particle(name, "와") or "와(과)")


def _gap_sentence(rows: Sequence[dict], i: int) -> str:
    own = rows[i]
    if i == 0:
        if len(rows) < 2:
            return ""
        second = rows[1]
        diff = (own.get("pts") or 0) - (second.get("pts") or 0)
        if diff > 0:
            return f"2위 {_name(second)}보다 승점 {diff}점 앞선 선두입니다."
        return f"2위 {_with(second)} 승점은 같지만 {_tiebreak(own, second)}에서 앞서 선두를 지키고 있습니다."
    above = rows[i - 1]
    who = "선두" if i == 1 else f"{i}위"
    diff = (above.get("pts") or 0) - (own.get("pts") or 0)
    if diff > 0:
        return f"{who} {_name(above)}보다 승점 {diff}점 뒤져 있습니다."
    return f"{who} {_with(above)} 승점은 같지만 {_tiebreak(above, own)}에서 밀립니다."


def _gd(row: dict) -> str:
    gd = row.get("goalConDiff") or 0
    return f"+{gd}" if gd > 0 else str(gd)


def standings(overview: Optional[dict], fixtures: Optional[List[dict]], end: datetime,
              team_name: str) -> Tuple[Optional[List[str]], str]:
    """Markdown lines for the club's league position, or (None, why not)."""
    league = (overview or {}).get("league") or {}
    rows = sorted(league.get("rows") or [], key=lambda r: r.get("idx") or 99)
    i = _own_row(rows, (overview or {}).get("team_id"), team_name)
    if i is None:
        return None, "no table row for the club"
    own = rows[i]
    if not own.get("played"):
        return None, "season not started"
    finished = _finished_league_fixtures(fixtures, league, end)
    if finished is None:
        return None, "no fixture list to check the table against"
    if finished != own["played"]:
        return None, f"table not up to date ({own['played']} played, {finished} finished)"

    lo = max(0, min(i - 1, len(rows) - 3))
    table = ["| 순위 | 팀 | 경기 | 승점 | 득실 |", "|---|---|---|---|---|"]
    for row in rows[lo:lo + 3]:
        name = f"**{_name(row)}**" if row is own else _name(row)
        table.append(f"| {row.get('idx')} | {name} | {row.get('played')} | {row.get('pts')} | {_gd(row)} |")
    lines = [f"**{own.get('idx')}위 · {own['played']}경기 승점 {own.get('pts')}**", ""]
    gap = _gap_sentence(rows, i)
    if gap:
        lines += [gap, ""]
    return lines + table, "rendered"


# ─────────────────────────── fixtures ───────────────────────────────────────

def next_fixtures(fixtures: Optional[List[dict]], end: datetime, team_name: str, limit: int = 2) -> List[str]:
    """'11월 5일(목) 새벽 5시 · Slavia Prague 원정 · Champions League' for the
    next unplayed fixtures from the edition's end, any competition."""
    upcoming = []
    for f in fixtures or []:
        kickoff = fixture_kickoff(f)
        if kickoff and kickoff >= end and not f.get("finished") and not f.get("cancelled") and not f.get("date_tbd"):
            upcoming.append((kickoff, f))
    lines = []
    for kickoff, f in sorted(upcoming, key=lambda kf: kf[0])[:limit]:
        at_home = normalize(canonical(f.get("home") or "") or f.get("home") or "") == normalize(team_name)
        parts = [kst_label(kickoff, bool(f.get("time_tbd"))), f"{_md(f.get('opponent'))} {'홈' if at_home else '원정'}"]
        if f.get("tournament"):
            parts.append(_md(f["tournament"]))
        lines.append(" · ".join(parts))
    return lines


# ─────────────────────────── injuries ───────────────────────────────────────

def return_label(raw: Optional[str], today: date) -> Tuple[str, int]:
    """FotMob's expected return ("Mid December 2026") in Korean, and a sort key."""
    raw = (raw or "").strip()
    if raw == "Doubtful":
        return "출전 불투명", 0
    if raw == "Back in training":
        return "훈련 복귀", 1
    if re.fullmatch(r"Out for (?:the )?season", raw, re.IGNORECASE):
        return "시즌 아웃", 8_999_999
    m = re.fullmatch(r"(?:About |In )?(a|an|one|two|three|four|five|six|\d+|a few) (week|month)s?", raw, re.IGNORECASE)
    if m:
        n = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}.get(m.group(1).lower())
        count = "몇" if m.group(1).lower() == "a few" else str(n or int(m.group(1)))
        unit = "주" if m.group(2).lower() == "week" else "개월"
        days = (3 if count == "몇" else int(count)) * (7 if unit == "주" else 30)
        when = today + timedelta(days=days)
        label = f"몇 {unit} 뒤 복귀 예상" if count == "몇" else f"약 {count}{unit} 뒤 복귀 예상"
        return label, when.year * 10_000 + when.month * 100 + when.day
    m = re.fullmatch(r"(Early|Mid|Late) ([A-Za-z]+) (\d{4})", raw)
    if m and m.group(2) in _MONTHS:
        part, day = _PART[m.group(1)]
        month, year = _MONTHS[m.group(2)], int(m.group(3))
        if date(year, month, day) < today - timedelta(days=10):
            return "복귀 시점 미정", 9_000_000   # FotMob's date has passed; still listed as out
        when = f"{month}월 {part}" if year == today.year else f"{year}년 {month}월 {part}"
        return f"{when} 복귀 예상", year * 10_000 + month * 100 + day
    if raw and raw != "Unknown":
        print(f"  ⚠ unrecognised FotMob return date {raw!r}, shown as 미정")
    return "복귀 시점 미정", 9_000_001


def _position(player: dict) -> Optional[str]:
    first = (player.get("positions") or "").split(",")[0].strip()
    return _POSITIONS.get(first) or _ROLES.get(player.get("role") or "")


def injuries(overview: Optional[dict], today: date) -> List[str]:
    """'Bukayo Saka · 오른쪽 윙어 · 12월 중순 복귀 예상', soonest return first."""
    listed = []
    for player in (overview or {}).get("injuries") or []:
        if not player.get("name"):
            continue
        label, key = return_label(player.get("expected_return"), today)
        parts = [_md(player["name"])] + ([p] if (p := _position(player)) else []) + [label]
        listed.append((key, " · ".join(parts)))
    lines = [line for _, line in sorted(listed, key=lambda kl: kl[0])]
    if len(lines) > MAX_INJURIES:
        lines = lines[:MAX_INJURIES] + [f"외 {len(lines) - MAX_INJURIES}명"]
    return lines


# ─────────────────────────── the blocks ─────────────────────────────────────

def render(overview: Optional[dict], fixtures: Optional[List[dict]], end: datetime,
           team_name: str) -> Tuple[str, Dict[str, str]]:
    """The Markdown for both blocks ('' if neither has data) and, per block,
    'rendered' or why it was left out (kept in inputs/{team}.json)."""
    standing_lines, standing_reason = (standings(overview, fixtures, end, team_name) if overview
                                       else (None, "no FotMob overview collected after the edition's end"))
    fixture_lines = next_fixtures(fixtures, end, team_name)
    today = end.astimezone(KST).date()
    injury_lines = injuries(overview, today) if overview else []

    out: List[str] = []
    if standing_lines and fixture_lines:
        out += [sections.STANDINGS_AND_FIXTURES, ""] + standing_lines + ["", "**다음 경기**", ""]
        out += [f"- {line}" for line in fixture_lines]
    elif standing_lines:
        out += [sections.STANDINGS, ""] + standing_lines
    elif fixture_lines:
        out += [sections.FIXTURES, ""] + [f"- {line}" for line in fixture_lines]
    if injury_lines:
        out += (["", ""] if out else []) + [sections.INJURIES, ""] + [f"- {line}" for line in injury_lines]

    info = {
        "standings": standing_reason,
        "fixtures": f"{len(fixture_lines)} upcoming" if fixture_lines else "no upcoming fixture",
        "injuries": (f"{len(injury_lines)} listed" if injury_lines
                     else "none injured" if overview else "no FotMob overview collected after the edition's end"),
    }
    return "\n".join(out), info
