"""
Metric 2 — Section Completeness
Checks whether the sections this week's source calls for are present and
valid: the three match sections when there were matches, 이적 & 뉴스 when
there was news, and the 이번 주 휴식 fallback when there was neither. (It
used to expect all four every week, so a news-only week could never pass.)

The 'transfers' section only counts as present when no LLM drift is detected —
a drift response that mentions the word 이적 should not be counted as a
properly generated transfers section.

Result keys
-----------
score       : float          — fraction of expected sections present (0.0 – 1.0)
hits        : dict[str, bool] — per-section pass/fail
"""

import re
from typing import Dict

from evaluate.utils import extract_newsletter_matches

# Each key maps to a regex that must match somewhere in the newsletter text.
# Note: "match_week" intentionally checks for "베스트 경기" (the locked heading
# text from prompt.yml), not the generic "이번 주" — that phrase also appears
# in the headline heading ("## 🏆 이번 주 헤드라인"), which made the two checks
# indistinguishable and let a missing match-of-the-week section go undetected.
# "scoreboard" is validated separately via extract_newsletter_matches, which
# actually parses the table instead of just matching its header text.
SECTIONS: Dict[str, re.Pattern] = {
    "headline":     re.compile(r"##.*(헤드라인|Headline)"),
    "match_week":   re.compile(r"##.*(베스트\s*경기|Match of the Week)"),
    "transfers":    re.compile(r"^##\s.*(이적|Transfer)", re.MULTILINE | re.IGNORECASE),
    "quiet_week":   re.compile(r"^##\s.*휴식", re.MULTILINE),
}


def evaluate(newsletter_text: str, drift_detected: bool,
             has_matches: bool = True, has_news: bool = True) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file
        drift_detected:  result of llm_drift.evaluate()["detected"]
        has_matches:     the edition's source had at least one match
        has_news:        the edition's source had headlines or transfers
    Returns:
        {"score": float, "hits": {section_name: bool}}
    """
    hits: Dict[str, bool] = {}
    if has_matches:
        hits["headline"] = bool(SECTIONS["headline"].search(newsletter_text))
        hits["match_week"] = bool(SECTIONS["match_week"].search(newsletter_text))
        hits["scoreboard"] = bool(extract_newsletter_matches(newsletter_text))
    if has_news:
        # Only counts if the LLM actually generated transfer content
        hits["transfers"] = (not drift_detected) and bool(SECTIONS["transfers"].search(newsletter_text))
    if not hits:
        hits["quiet_week"] = bool(SECTIONS["quiet_week"].search(newsletter_text))

    score = sum(hits.values()) / len(hits)
    return {"score": score, "hits": hits}
