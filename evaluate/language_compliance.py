"""
Metric 5 — Language Compliance
Measures the fraction of alphabetic characters in the newsletter that are
Korean, after removing the English the style guide *requires*: proper nouns
(team, player, manager, outlet names) and link targets.

Counting those names made the old ratio top out around 65% on every edition,
however well written, so it could never pass its 80% target. What's left
after removing them should be Korean; English that survives is real drift
("senior players가", "Belgian international로서").

Result keys
-----------
ratio       : float  — Korean chars / remaining alpha chars (0.0 – 1.0)
target      : float  — minimum acceptable ratio
passed      : bool   — ratio >= target
"""

import re
from typing import Dict

from evaluate.utils import strip_links

_TARGET = 0.95

# Capitalised words and the name particles inside them ("Virgil van Dijk",
# "Kevin De Bruyne", "Martin Ødegaard", "BBC"). Latin letters only, so a
# trailing Korean particle ("Bruyne는") is kept and counted as Korean.
_PROPER_NOUN_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÿ'\-]*"
    r"(?:\s+(?:(?:van|von|de|der|den|da|di|du|dos|del|la|le)\s+)*[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÿ'\-]*)*"
)
# Lower-case English the format itself uses: "Arsenal vs Liverpool", "xG".
_ALLOWED_RE = re.compile(r"(?<![A-Za-z])(?:vs|xG)(?![A-Za-z])")


def evaluate(newsletter_text: str) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file
    Returns:
        {"ratio": float, "target": float, "passed": bool}
    """
    text = _ALLOWED_RE.sub(" ", _PROPER_NOUN_RE.sub(" ", strip_links(newsletter_text)))
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return {"ratio": 0.0, "target": _TARGET, "passed": False}

    korean = sum(
        1 for c in alpha
        if '가' <= c <= '힣' or 'ㄱ' <= c <= 'ㆎ'
    )
    ratio = korean / len(alpha)
    return {"ratio": ratio, "target": _TARGET, "passed": ratio >= _TARGET}
