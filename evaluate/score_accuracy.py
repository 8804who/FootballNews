"""
Metric 1 — Score Accuracy
Compares match scores in the newsletter against fotmob source data.

Team names are compared by club, not by string: the source says "Manchester
United" where the model (copying FotMob's stats table) writes "Man United",
and before this was alias-aware every such match counted as wrong.

Rows that match no source match (last week's game shown again, or an invented
one) count against the score too: correct / (source matches + extra rows).

Result keys
-----------
score       : float | None  — correct rows / (source matches + extra rows)
details     : list of (match_tuple, bool)  — per-match pass/fail
wrong       : list of (match_tuple, row)   — on the scoreboard with another score
missing     : list of match_tuple          — not on the scoreboard at all
extra_rows  : list of row                  — scoreboard rows matching no source
                                             match (a repeat or invented game)
"""

from typing import Dict, List, Optional, Tuple

from evaluate.utils import extract_newsletter_matches
from team_names import canonical, distinctive_words, normalize

Match = Tuple[str, str, int, int]


def same_team(a: str, b: str) -> bool:
    """Whether two spellings name the same club ("Man United" / "Manchester
    United", "Nottm Forest" / "Nottingham Forest", "Bayern" / "Bayern München")."""
    ca, cb = canonical(a), canonical(b)
    if ca or cb:
        return ca == cb
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    return bool(distinctive_words(a) & distinctive_words(b))


def _orientation(source: Match, row: Match) -> Optional[bool]:
    """True if row lists the same two teams in the same order, False if
    reversed, None if it's a different fixture."""
    if same_team(source[0], row[0]) and same_team(source[1], row[1]):
        return True
    if same_team(source[0], row[1]) and same_team(source[1], row[0]):
        return False
    return None


def compare_scoreboard(source: List[Match], rows: List[Match]) -> Dict:
    """Match each source fixture to a scoreboard row and check its score."""
    ok: List[Match] = []
    wrong: List[Tuple[Match, Match]] = []
    missing: List[Match] = []
    used = set()
    for m in source:
        hit = None
        for i, r in enumerate(rows):
            same_order = _orientation(m, r)
            if i in used or same_order is None:
                continue
            score = (r[2], r[3]) if same_order else (r[3], r[2])
            hit = (i, r, score == (m[2], m[3]))
            if hit[2]:
                break
        if hit is None:
            missing.append(m)
            continue
        index, row, correct = hit
        used.add(index)
        if correct:
            ok.append(m)
        else:
            wrong.append((m, row))
    extra = [r for i, r in enumerate(rows) if i not in used]
    return {"ok": ok, "wrong": wrong, "missing": missing, "extra": extra}


def evaluate(
    fotmob_matches: List[Match],
    newsletter_text: str,
) -> Dict:
    """
    Args:
        fotmob_matches: ground-truth list from load_fotmob_for_team()
        newsletter_text: full text of the newsletter file
    Returns:
        {"score": float | None, "details": [(match, ok), ...], "wrong": [...],
         "missing": [...], "extra_rows": [...]}
    """
    rows = extract_newsletter_matches(newsletter_text)
    result = compare_scoreboard(fotmob_matches, rows)
    if not fotmob_matches and not result["extra"]:
        return {"score": None, "details": [], "wrong": [], "missing": [], "extra_rows": []}

    ok = set(result["ok"])
    details = [(m, m in ok) for m in fotmob_matches]
    score = len(result["ok"]) / (len(fotmob_matches) + len(result["extra"]))

    return {
        "score": score,
        "details": details,
        "wrong": result["wrong"],
        "missing": result["missing"],
        "extra_rows": result["extra"],
    }
