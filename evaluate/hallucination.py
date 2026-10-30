"""
Metric 4 — Hallucination Rate
Measures the fraction of English proper nouns in the newsletter that cannot
be traced back to the source data (i.e., the LLM invented them).

Strategy: extract all multi-word English capitalised sequences from the
newsletter; for each one, check whether any of its word parts appear in the
pool of player names extracted from the source files.  A name is flagged as
hallucinated only when *none* of its parts match any source name.

Competitions, outlets and the configured clubs (in any spelling) aren't
people and are skipped — they made up most of the old false alarms
("Champions League", "Sky Sports", "Man Utd").

Result keys
-----------
rate                : float | None  — hallucinated / total candidate names
hallucinated_names  : set[str]      — names not found in source
total_names         : int           — total candidate names extracted
"""

import re
from typing import Dict, Optional, Set

from team_names import canonical

# Two-or-more capitalised words → likely a person name. Lookarounds rather
# than \b: Hangul counts as a word character, so in "Kevin De Bruyne는" there
# is no word boundary after the name and \b cut it down to "Kevin De".
_EN_NAME_RE = re.compile(
    r'(?<![A-Za-zÀ-ÿ])[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ\-\']*'
    r'(?:\s+[A-ZÀ-ÖØ-Þ][a-zß-öø-ÿ\-\']+)+(?![A-Za-zÀ-ÿ])'
)

_STOPWORDS: Set[str] = {
    "Weekly Report", "Match Stats",
    "Ball Possession", "Total Shots", "Expected Goals",
    "Player Substitution", "Red Card", "Yellow Card", "Own Goal",
    "No Match",
}

# A sequence containing one of these words is a competition, outlet or label.
_NON_PERSON_WORDS: Set[str] = {
    "League", "Cup", "Shield", "Trophy", "Round", "Stage", "Final",
    "Sky", "Sports", "Sport", "BBC", "Athletic", "Paper", "Talk", "News",
    "Premier", "Transfer", "Transfers", "Official",
}


def extract_names(text: str) -> Set[str]:
    """Capitalised multi-word sequences that could be people."""
    names: Set[str] = set()
    for n in _EN_NAME_RE.findall(text):
        if n in _STOPWORDS or len(n) <= 5:
            continue
        if any(word in _NON_PERSON_WORDS for word in n.split()):
            continue
        if canonical(n):
            continue  # one of our clubs, in any spelling
        names.add(n)
    return names


def evaluate(newsletter_text: str, source_players: Set[str]) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file
        source_players:  set of player name strings from load_fotmob_for_team()
    Returns:
        {"rate": float | None, "hallucinated_names": set, "total_names": int}
    """
    nl_names = extract_names(newsletter_text)

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
