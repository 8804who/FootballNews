"""
Metric 4 — Hallucination Rate
Measures the fraction of English proper nouns in the newsletter that cannot
be traced back to the fotmob source data (i.e., the LLM invented them).

Strategy: extract all multi-word English capitalised sequences from the
newsletter; for each one, check whether any of its word parts appear in the
pool of player names extracted from the source files.  A name is flagged as
hallucinated only when *none* of its parts match any source name.

Result keys
-----------
rate                : float | None  — hallucinated / total candidate names
hallucinated_names  : set[str]      — names not found in source
total_names         : int           — total candidate names extracted
"""

import re
from typing import Dict, Optional, Set

# Two-or-more capitalised words → likely a person name
_EN_NAME_RE = re.compile(
    r'\b[A-Z][a-záéíóúàèìòùäöüñ\-\']*'
    r'(?:\s+[A-Z][a-záéíóúàèìòùäöüñ\-\']+)+\b'
)

_STOPWORDS: Set[str] = {
    "Premier League", "FA Cup", "Weekly Report", "Match Stats",
    "Ball Possession", "Total Shots", "Expected Goals",
    "Player Substitution", "Red Card", "Yellow Card", "Own Goal",
    "No Match",
}


def _extract_en_names(text: str) -> Set[str]:
    found = _EN_NAME_RE.findall(text)
    return {n for n in found if n not in _STOPWORDS and len(n) > 5}


def evaluate(newsletter_text: str, source_players: Set[str]) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file
        source_players:  set of player name strings from load_fotmob_for_team()
    Returns:
        {"rate": float | None, "hallucinated_names": set, "total_names": int}
    """
    nl_names = _extract_en_names(newsletter_text)

    if not nl_names or not source_players:
        return {"rate": None, "hallucinated_names": set(), "total_names": len(nl_names)}

    # Exact-word membership, not substring containment — a substring check
    # (e.g. "cole" in "james coleman") produces false negatives that let
    # genuinely hallucinated names slip through undetected.
    source_words = {w.lower() for name in source_players for w in name.split()}
    hallucinated = {
        n for n in nl_names
        if not any(part.lower() in source_words for part in n.split())
    }

    rate: Optional[float] = len(hallucinated) / len(nl_names)
    return {
        "rate": rate,
        "hallucinated_names": hallucinated,
        "total_names": len(nl_names),
    }
