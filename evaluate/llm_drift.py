"""
Metric 3 — LLM Drift
Detects whether the LLM produced a chatbot-style response (asking the user
for more data) instead of generating newsletter content.

This most commonly appears in the transfers section when the source contains
"There is no transfer news this week." — the model ignores the instruction
to fall back gracefully and instead requests user input.

Result keys
-----------
detected    : bool        — True if drift was found
signals     : list[str]   — which patterns triggered
"""

import re
from typing import Dict, List

# Each pattern corresponds to a phrasing the model uses when going off-script.
_PATTERNS: List[re.Pattern] = [re.compile(p) for p in [
    r"알려주세요",
    r"붙여\s*(?:넣기|주세요)",
    r"제가\s*정확히\s*알아야",
    r"입력\s*형식",
    r"원하시는\s*입력",
    r"다음\s*중\s*하나를\s*골라",
    r"이적\s*관련\s*원자료",
    r"확정\s*이적.*최대\s*\d+",
    r"원하시면\s*다음",
]]


def evaluate(newsletter_text: str) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file
    Returns:
        {"detected": bool, "signals": [matched pattern strings]}
    """
    triggered = [p.pattern for p in _PATTERNS if p.search(newsletter_text)]
    return {"detected": bool(triggered), "signals": triggered}
