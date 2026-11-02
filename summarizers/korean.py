"""Korean particles after English club names.

Names stay in English in the newsletter, so the particle after one depends
on how it's *said*: "Arsenal과" (아스널), "Chelsea와" (첼시), and
"Arsenal로" (a final ㄹ takes 로, not 으로). The model guesses from the
spelling and gets it wrong ("Newcastle와", "Bayern München와"); the readings
in teams.yml make it deterministic for clubs. Players are left to the model.
"""

import re
from functools import lru_cache
from typing import Dict, Optional, Tuple

from yaml import safe_load

from team_names import TEAMS_YML

# particle as written → (after a final consonant, after a vowel)
_PAIRS = {
    "이": ("이", "가"), "가": ("이", "가"),
    "을": ("을", "를"), "를": ("을", "를"),
    "은": ("은", "는"), "는": ("은", "는"),
    "과": ("과", "와"), "와": ("과", "와"),
    "으로": ("으로", "로"), "로": ("으로", "로"),
}


@lru_cache(maxsize=None)
def readings() -> Dict[str, str]:
    data = safe_load(TEAMS_YML.read_text(encoding="utf-8")) or {}
    return dict(data.get("readings") or {})


def final_consonant(name: str) -> Optional[str]:
    """'' (ends in a vowel), 'ㄹ', or 'other' for a club in teams.yml; None
    for a name we don't know how to say."""
    reading = readings().get(name)
    syllables = [c for c in reading or "" if "가" <= c <= "힣"]
    if not syllables:
        return None
    jong = (ord(syllables[-1]) - ord("가")) % 28
    return "" if jong == 0 else "ㄹ" if jong == 8 else "other"


def particle(name: str, written: str) -> Optional[str]:
    """The particle that agrees with `name` ("Arsenal", "와" → "과"), or None."""
    final = final_consonant(name)
    if final is None or written not in _PAIRS:
        return None
    after_consonant, after_vowel = _PAIRS[written]
    if written in ("으로", "로"):
        return "으로" if final == "other" else "로"
    return after_consonant if final else after_vowel


@lru_cache(maxsize=None)
def _name_re() -> re.Pattern:
    names = sorted(readings(), key=len, reverse=True)
    alternation = "|".join(re.escape(n) for n in names)
    # A particle stands alone when Hangul doesn't follow it ("Arsenal이" yes,
    # "Arsenal이라는" no); 와/과 may take 의 ("Chelsea와의").
    return re.compile(
        rf"(?<![A-Za-zÀ-ÿ])({alternation})(으로|로|이|가|을|를|은|는|과|와)(?=의(?![가-힣])|(?![가-힣]))"
    )


def fix_particles(text: str) -> Tuple[str, int]:
    """Text with every particle after a known club name made to agree, and
    the number changed."""
    changed = 0

    def repl(m):
        nonlocal changed
        right = particle(m.group(1), m.group(2))
        if right is None or right == m.group(2):
            return m.group(0)
        changed += 1
        return m.group(1) + right

    return _name_re().sub(repl, text), changed
