"""
Metric 1 — Score Accuracy
Compares match scores in the newsletter against fotmob source data.

Result keys
-----------
score       : float | None  — fraction of source matches correctly reported
details     : list of (match_tuple, bool)  — per-match pass/fail
"""

from typing import Dict, List, Optional, Tuple

from evaluate.utils import extract_newsletter_matches


def evaluate(
    fotmob_matches: List[Tuple[str, str, int, int]],
    newsletter_text: str,
) -> Dict:
    """
    Args:
        fotmob_matches: ground-truth list from load_fotmob_for_team()
        newsletter_text: full text of the newsletter file
    Returns:
        {"score": float | None, "details": [(match, ok), ...]}
    """
    if not fotmob_matches:
        return {"score": None, "details": []}

    nl_matches = extract_newsletter_matches(newsletter_text)
    nl_set = set(nl_matches)

    details = [(m, m in nl_set) for m in fotmob_matches]
    matched = sum(ok for _, ok in details)
    score = matched / len(fotmob_matches)

    return {"score": score, "details": details}
