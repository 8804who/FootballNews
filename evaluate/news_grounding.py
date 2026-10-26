"""
Metric 6 — News Grounding
Checks that every item in the newsletter's "이적 & 뉴스" section traces back to
this week's source data (Google News RSS headlines + FotMob transfers).

An item (bullet / bold line) is "grounded" when at least half of the English
proper-noun tokens it mentions appear in the source pool. Items with no
English proper nouns can't be checked and are skipped. This catches few-shot
example leakage and invented rumors that the match-focused metrics can't see.

Result keys
-----------
score       : float | None — grounded / checked items (None if nothing checkable)
items       : list[(str, bool)] — (item text, grounded?) for each checked item
ungrounded  : list[str]         — items that failed the check
"""

import re
from typing import Dict, List, Set

_SECTION_RE = re.compile(r"^##\s.*(이적|뉴스)", re.MULTILINE)
_TOKEN_RE = re.compile(r"\b[A-Z][A-Za-zÀ-ÿ'\-]{2,}\b")

# Publisher / generic words that appear in nearly every item and carry no signal.
_IGNORE: Set[str] = {
    "Sky", "Sports", "BBC", "Athletic", "The", "Premier", "League", "Paper",
    "Talk", "Transfer", "Centre", "Official", "News", "Rumors",
}


def extract_news_section(text: str) -> str:
    """Return the '이적 & 뉴스' section (from its H2 heading to the next H2 / EOF)."""
    m = _SECTION_RE.search(text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s(?!#)", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def build_source_words(source_text: str, extra_names: Set[str]) -> Set[str]:
    words = {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ'\-]+", source_text)}
    for name in extra_names:
        words.update(w.lower() for w in name.split())
    return words


def evaluate(newsletter_text: str, source_words: Set[str]) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file
        source_words:    lower-cased words from RSS + transfers + fotmob names
    """
    section = extract_news_section(newsletter_text)
    items: List[tuple] = []
    if section and source_words:
        for line in section.splitlines():
            s = line.strip()
            if not (s.startswith(("-", "*")) or s.startswith("**")):
                continue
            tokens = [t for t in _TOKEN_RE.findall(s) if t not in _IGNORE]
            if not tokens:
                continue
            hit = sum(1 for t in tokens if t.lower() in source_words)
            items.append((s, hit / len(tokens) >= 0.5))

    score = (sum(ok for _, ok in items) / len(items)) if items else None
    return {
        "score": score,
        "items": items,
        "ungrounded": [t for t, ok in items if not ok],
    }
