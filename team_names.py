"""Resolve the different spellings of a club to the name setting.yml uses.

FotMob writes "Man United", headlines say "Man Utd" or "Spurs", the model
copies whichever it saw, and sign-up form answers arrive as typed
("TottenhamHotspur", "토트넘"). Every comparison of club names goes through
here so they all agree; the spellings themselves live in teams.yml.
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set

from yaml import safe_load

TEAMS_YML = Path(__file__).resolve().parent / "teams.yml"

# Words too common across club names to identify one ("Leeds United" and
# "Man United" share "united"; "Real Madrid" and "Real Betis" share "real").
_GENERIC_WORDS: Set[str] = {
    "united", "city", "town", "county", "real", "athletic", "atletico",
    "sporting", "inter", "olympique", "borussia", "hotspur", "albion",
    "rovers", "wanderers", "manchester", "club", "deportivo",
}


def fold(text: str) -> str:
    """Lower-case and strip accents ("München" → "munchen"); Hangul is kept."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", stripped).lower()


def normalize(name: str) -> str:
    """Comparison key: folded, no "FC"/"AFC", no spaces or punctuation."""
    s = re.sub(r"\b(?:a?fc)\b", "", fold(name))
    return re.sub(r"[\W_]+", "", s)


def distinctive_words(name: str) -> Set[str]:
    """Words of a club name that identify it ("Nottm Forest" → {"nottm", "forest"})."""
    return {
        w for w in re.findall(r"[^\W\d_]+", fold(name))
        if len(w) >= 4 and w not in _GENERIC_WORDS
    }


@lru_cache(maxsize=None)
def _spellings() -> Dict[str, List[str]]:
    data = safe_load(TEAMS_YML.read_text(encoding="utf-8")) or {}
    by_team = {t["name"]: [t["name"]] for t in data.get("fotmob", {}).get("teams", [])}
    for team, names in (data.get("aliases") or {}).items():
        by_team.setdefault(team, [team]).extend(names)
    return by_team


@lru_cache(maxsize=None)
def _index() -> Dict[str, str]:
    return {normalize(n): team for team, names in _spellings().items() for n in names}


def canonical(name: str) -> Optional[str]:
    """The configured club `name` refers to, or None if it isn't one of them."""
    return _index().get(normalize(name or ""))


def aliases(team: str) -> List[str]:
    """Every known spelling of `team`, including its own name."""
    return list(_spellings().get(team, [team]))
