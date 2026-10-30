"""
Metric 6 — News Grounding
Checks that every item in the newsletter's "이적 & 뉴스" section traces back to
this week's source data (Google News RSS headlines + FotMob transfers).

An item (bullet or paragraph) is "grounded" when at least half of the English
proper-noun tokens it mentions appear in its source. Since the newsletter
links each item to the headline(s) it was written from, the source for a
linked item is *those* headlines — so an item that names the right players
but links to a different story fails. Unlinked items (FotMob transfers,
older editions) are checked against the whole week's pool. Items with no
English proper nouns can't be checked and are skipped. This catches few-shot
example leakage and invented rumors that the match-focused metrics can't see.

Result keys
-----------
score       : float | None — grounded / checked items (None if nothing checkable)
items       : list[(str, bool)] — (item text, grounded?) for each checked item
ungrounded  : list[str]         — items that failed the check
"""

import re
from typing import Dict, List, Optional, Set

from evaluate.utils import extract_links, strip_links
from team_names import canonical

_SECTION_RE = re.compile(r"^##\s.*(이적|뉴스)", re.MULTILINE)
# Lookarounds rather than \b: Hangul is a word character, so a name followed
# by a particle ("Sancho가") has no word boundary and \b skipped it entirely.
_TOKEN_RE = re.compile(r"(?<![A-Za-zÀ-ÿ])[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÿ'\-]{2,}(?![A-Za-zÀ-ÿ])")

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


def split_news_items(section: str) -> List[str]:
    """Bullets and paragraphs of a news section, with sub-headings left out."""
    body = re.sub(r"^###.*$", "", section, flags=re.MULTILINE)
    return [item.strip() for item in re.split(r"\n(?=\s*[-*] )|\n\s*\n", body) if item.strip()]


def build_source_words(source_text: str, extra_names: Set[str]) -> Set[str]:
    words = {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ'\-]+", source_text)}
    for name in extra_names:
        words.update(w.lower() for w in name.split())
    return words


def evaluate(
    newsletter_text: str,
    source_words: Set[str],
    headline_words: Optional[Dict[str, Set[str]]] = None,
) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file, links included
        source_words:    lower-cased words from RSS + transfers + fotmob names
        headline_words:  {headline URL: its lower-cased words}, for linked items
    """
    section = extract_news_section(newsletter_text)
    items: List[tuple] = []
    if section and (source_words or headline_words):
        for item in split_news_items(section):
            urls = [url for _, url in extract_links(item)]
            tokens = [t for t in _TOKEN_RE.findall(strip_links(item))
                      if t not in _IGNORE and not canonical(t)]
            if not tokens:
                continue
            if urls and headline_words is not None:
                pool = set().union(*(headline_words.get(u, set()) for u in urls))
            else:
                pool = source_words
            hit = sum(1 for t in tokens if t.lower() in pool)
            items.append((item, hit / len(tokens) >= 0.5))

    score = (sum(ok for _, ok in items) / len(items)) if items else None
    return {
        "score": score,
        "items": items,
        "ungrounded": [t for t, ok in items if not ok],
    }
