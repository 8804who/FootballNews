"""
Metric 2 — Section Completeness
Checks whether all four required newsletter sections are present and valid.

The 'transfers' section only counts as present when no LLM drift is detected —
a drift response that mentions the word 이적 should not be counted as a
properly generated transfers section.

Result keys
-----------
score       : float          — fraction of sections present (0.0 – 1.0)
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
    "transfers":    re.compile(r"이적|Transfer", re.IGNORECASE),
}


def evaluate(newsletter_text: str, drift_detected: bool) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file
        drift_detected:  result of llm_drift.evaluate()["detected"]
    Returns:
        {"score": float, "hits": {section_name: bool}}
    """
    hits: Dict[str, bool] = {
        "headline":   bool(SECTIONS["headline"].search(newsletter_text)),
        "match_week": bool(SECTIONS["match_week"].search(newsletter_text)),
        "scoreboard": bool(extract_newsletter_matches(newsletter_text)),
        # Only counts if the LLM actually generated transfer content
        "transfers":  (not drift_detected) and bool(SECTIONS["transfers"].search(newsletter_text)),
    }

    score = sum(hits.values()) / len(hits)
    return {"score": score, "hits": hits}
