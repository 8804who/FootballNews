"""
Metric 5 — Language Compliance
Measures the fraction of alphabetic characters in the newsletter that are
Korean.  The prompt requires Korean output with English-only proper nouns,
so a well-formed newsletter should score above ~80%.

Result keys
-----------
ratio       : float  — Korean chars / total alpha chars (0.0 – 1.0)
target      : float  — minimum acceptable ratio (0.80)
passed      : bool   — ratio >= target
"""

from typing import Dict


_TARGET = 0.80


def evaluate(newsletter_text: str) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file
    Returns:
        {"ratio": float, "target": float, "passed": bool}
    """
    alpha = [c for c in newsletter_text if c.isalpha()]
    if not alpha:
        return {"ratio": 0.0, "target": _TARGET, "passed": False}

    korean = sum(
        1 for c in alpha
        if '\uAC00' <= c <= '\uD7A3' or '\u3131' <= c <= '\u318E'
    )
    ratio = korean / len(alpha)
    return {"ratio": ratio, "target": _TARGET, "passed": ratio >= _TARGET}
