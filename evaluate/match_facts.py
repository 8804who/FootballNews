"""
Metric 7 — Match Facts
Checks every "minute + player" claim in the match part of the newsletter
(headline, match story, scoreboard one-liners) against the match events in
the source: "64분에 Jurriën Timber가 포문을 열자" passes only if the source has
an event for Timber at 64'.

Score accuracy catches a wrong scoreline; this catches the story around it —
a goal credited to the wrong player, a made-up minute, an event for someone
who wasn't in the match.

How a claim is read: each minute ("64분", "90+6분", "46'", "후반 3분" = 48')
in the match story and scoreboard is paired with the player its clause
attributes it to (see _agent). Skipped: the headline (often figurative —
"초반 2분의 충격을 뒤집은 Arsenal, Ødegaard의 한 방"), durations and ranges
("7분 사이에", "3분 뒤", "79분까지"), goals conceded ("29분 연속 실점"), and
minutes in a clause that names no player. "N분 만에" can be a match minute
or the time since a substitution, so it only counts when it checks out.

Calibrated on 78 real editions: apart from claims about matches repeated
from the previous week, it found one real error that went out (Aug 31,
Man United — Jacob Greaves' own goal credited to Bruno Fernandes' hat-trick).

Result keys
-----------
score   : float | None — verified / checked claims (None if nothing checkable)
checked : int          — claims checked
failed  : list[str]    — e.g. "64' Bukayo Saka — no event for him at that minute"
"""

import re
from typing import Dict, List, Optional, Sequence, Set, Tuple

from team_names import canonical, fold

# "- `64'` **Arsenal**:  - ⚽ Goal: Jurriën Timber (1 - 0) (assist by Declan Rice)"
_EVENT_RE = re.compile(
    r"^- `(\d+)(?:\+(\d+))?'` \*\*.+?\*\*:\s*-\s*\S+\s*"
    r"(Goal|Player Substitution|Yellow Card|Red Card[^:]*):\s*(.+)$",
    re.MULTILINE,
)
_SCORER_RE = re.compile(r"^(.+?)\s*\(\d+\s*-\s*\d+\)")
_ASSIST_RE = re.compile(r"assist by ([^)]+)\)")
_TEAMS_RE = re.compile(r"^\| Stat \| (.+?) \| (.+?) \|$|^## .*?Match: (?:vs|@) (.+)$", re.MULTILINE)
_NEWS_HEADING_RE = re.compile(r"^##\s.*(이적|뉴스)", re.MULTILINE)

# A match minute, optionally after 전반/후반; not part of a range ("64~71분")
# and not a duration ("7분 사이에", "3분 뒤").
_MINUTE_RE = re.compile(
    r"(?:(전반|후반)\s*)?(?<![\d+~\-])(\d{1,3})(?:\s*\+\s*(\d{1,2}))?\s*(?:분|['’′])"
    r"(?!\s*(?:사이|뒤|후|간|동안|정도|차|여|까지|부터))"
)
_SOFT_RE = re.compile(r"\s*만에")
# "7분·29분 연속 실점": the goals were conceded, not scored by a named player.
_CONCEDED_RE = re.compile(r"(?:\s*[·,]\s*\d{1,3}\s*(?:분|'))*\s*(?:에|째)?\s*(?:\S{1,3}\s+)?(?:연속\s*)?(?:실점|헌납)")
_HEADLINE_RE = re.compile(r"^##[^\n]*헤드라인[^\n]*\n.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
# Clause boundaries: a comma that isn't inside a list of minutes ("46', 90'"),
# or a connective ending ("넣었고 ", "앞섰지만 ", "몰아치며 ").
_CLAUSE_SPLIT_RE = re.compile(
    r"(?<!['’′분]),\s*|(?:(?<=고)|(?<=지만)|(?<=며)|(?<=면서)|(?<=는데)|(?<=으나))\s+"
)
_AFTER_GAP_RE = re.compile(r"(?:에|째)?\s*")              # "64분 Timber", "1분에 Barrios"
_BEFORE_GAP_RE = re.compile(r"(?:의|가|이|은|는|도)?\s*")  # "Ramón의 76분", "Paz가 2분에"
_SUBJECT_RE = re.compile(r"(?:가|이|은|는)(?![가-힣])")     # "Bruno가", "Isak이", "Rice는"
# Capitalised Latin words, alone or in a run ("Saka", "Jurriën Timber",
# "Virgil van Dijk"); all-caps tokens (VAR, BBC) don't count.
_NAME_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ'\-]+"
    r"(?:\s+(?:(?:van|von|de|der|den|da|di|du|dos|del|la|le)\s+)*[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ'\-]+)*"
)
_NOT_PEOPLE: Set[str] = {
    "premier", "league", "champions", "europa", "conference", "cup", "carabao",
    "stamford", "bridge", "anfield", "emirates", "etihad", "trafford", "park", "stadium",
}


def _tokens(name: str) -> Set[str]:
    return {w for w in re.findall(r"[^\W\d_]+", fold(name)) if len(w) >= 3}


def parse_events(blocks: Sequence[str]) -> List[Tuple[int, Set[str]]]:
    """(minute, name tokens) for every goal, assist, substitution and card."""
    events = []
    for block in blocks:
        for m in _EVENT_RE.finditer(block):
            minute = int(m.group(1)) + int(m.group(2) or 0)
            kind, rest = m.group(3), m.group(4)
            if kind == "Goal":
                scorer = _SCORER_RE.match(rest)
                names = [scorer.group(1) if scorer else rest]
                assist = _ASSIST_RE.search(rest)
                if assist and assist.group(1).strip() != "None":
                    names.append(assist.group(1))
            elif kind == "Player Substitution":
                names = rest.split("->")
            else:
                names = [rest]
            events.extend((minute, _tokens(n)) for n in names if n.strip())
    return events


def _team_tokens(blocks: Sequence[str]) -> Set[str]:
    tokens: Set[str] = set()
    for m in _TEAMS_RE.finditer("\n".join(blocks)):
        for name in m.groups():
            if name:
                tokens |= _tokens(name)
    return tokens


def _match_part(text: str) -> str:
    """Match story and scoreboard: before the news section, headline removed."""
    m = _NEWS_HEADING_RE.search(text)
    return _HEADLINE_RE.sub("", text[: m.start()] if m else text)


def _people(clause: str, teams: Set[str]) -> List[re.Match]:
    """Person names in a clause (club, opponent and venue names left out)."""
    people = []
    for m in _NAME_RE.finditer(clause):
        words = _tokens(m.group(0))
        if words and not canonical(m.group(0)) and not words <= (teams | _NOT_PEOPLE) and not words & _NOT_PEOPLE:
            people.append(m)
    return people


def _agent(clause: str, minute: re.Match, people: List[re.Match]) -> Optional[str]:
    """Who a minute is about. Pairing a minute with the *nearest* name gave
    false alarms ("8', 10'에 앞섰지만 … Kostoulas가", "67분 Eze 어시스트와 71분
    본인 득점"), so it follows Korean sentence structure instead: a name right
    after the minute ("64분 Timber", "1분에 Barrios"), else a name right before
    it joined by a particle ("Ramón의 76분", "Paz가 2분에"), else the subject of
    the clause ("…68분 연속 득점으로 Bruno가 해트트릭"). None if the clause
    names no one — the minute is about a team ("8'에 앞섰지만")."""
    for p in people:
        if p.start() >= minute.end() and _AFTER_GAP_RE.fullmatch(clause, minute.end(), p.start()):
            return p.group(0)
    for p in people:
        if p.end() <= minute.start() and _BEFORE_GAP_RE.fullmatch(clause, p.end(), minute.start()):
            return p.group(0)
    subjects = [p for p in people if _SUBJECT_RE.match(clause, p.end())]
    if subjects:
        return min(subjects, key=lambda p: abs(p.start() - minute.start())).group(0)
    return None


def extract_claims(text: str, blocks: Sequence[str]) -> List[Tuple[str, int, str, bool]]:
    """(minute as written, minute as a number, name, soft) for each minute in
    the match part whose player can be told from its clause."""
    teams = _team_tokens(blocks)
    claims = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", _match_part(text)):
        for clause in _CLAUSE_SPLIT_RE.split(sentence):
            people = _people(clause, teams)
            if not people:
                continue
            for minute in _MINUTE_RE.finditer(clause):
                if _CONCEDED_RE.match(clause, minute.end()):
                    continue
                name = _agent(clause, minute, people)
                if name is None:
                    continue
                base, added = int(minute.group(2)), int(minute.group(3) or 0)
                if minute.group(1) == "후반" and base < 45:
                    base += 45
                written = minute.group(2) + (f"+{added}" if added else "")
                soft = bool(_SOFT_RE.match(clause, minute.end()))
                claims.append((written, base + added, name, soft))
    return claims


def evaluate(newsletter_text: str, blocks: Sequence[str]) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file
        blocks:          this edition's match blocks (utils.load_match_blocks)
    Returns:
        {"score": float | None, "checked": int, "failed": [str]}
    """
    events = parse_events(blocks)
    if not events:
        return {"score": None, "checked": 0, "failed": []}
    known = set().union(*(names for _, names in events))

    checked, failed = 0, []
    for written, minute, name, soft in extract_claims(newsletter_text, blocks):
        words = _tokens(name)
        at_minute = any(abs(minute - m) <= 1 and words & names for m, names in events)
        if at_minute:
            checked += 1
        elif soft:
            continue  # "N분 만에" that doesn't check out may be time since a substitution
        elif words & known:
            checked += 1
            failed.append(f"{written}' {name} — no event for this player at that minute")
        elif len(name.split()) > 1:
            checked += 1
            failed.append(f"{written}' {name} — not in this week's match events")
    score: Optional[float] = (checked - len(failed)) / checked if checked else None
    return {"score": score, "checked": checked, "failed": failed}
