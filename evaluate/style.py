"""
style.py — how machine-written an edition's Korean reads (report-only).

Counts the habits prompt.yml tells the model to avoid ("banned"), plus a
second set the prompt never names ("held_out"). The prompt can push the
banned count to zero by construction; the held-out count shows whether the
model just swapped one tic for another. Neither is a weighted metric or a
gate check: style isn't a defect, and evaluate/harness.py shows both side by
side for prompt and model comparisons.

The code-rendered blocks and link URLs are left out; pass the raw model
output (inputs/{team}.json "raw") to measure the model before tidy().
"""

import re
from typing import Dict

import newsletter_sections as sections

BANNED = {
    "long dash": r"[—―]",
    "arrow": r"→|⇒",
    "~할 수 있습니다": r"수 있습니다",
    "~로 보입니다": r"(?:로|게|해) 보입니다",
    "~라는 신호": r"신호(?:입니다|로|라)",
    "가능성이 있": r"가능성이 (?:있|높|크)",
    "팬 입장/팬들 사이": r"팬(?:들)? ?(?:입장|사이)",
    "기대와 불안": r"기대와 (?:불안|우려)",
    "분위기를": r"분위기를",
    "작렬/폭발/꽂아": r"작렬|폭발|꽂아",
    "존재감": r"존재감",
    "서사": r"서사",
    "변수": r"변수",
    "빛났": r"빛났|빛난",
    "스포트라이트": r"스포트라이트",
    "모양새": r"모양새",
    "눈에 띄": r"눈에 (?:띄|띕|띈)",
    "~에 따르면": r"에 따르면",
    "~로 알려진": r"로 알려진",
    "이는/또한 (sentence start)": r"(?:^|[.!?]\s+)(?:이는|또한)\s",
    "passive 보도/제기됐습니다": r"(?:보도|제기|거론|확인|전해|언급)(?:되었|됐)습니다",
}

HELD_OUT = {
    "한편": r"(?:^|\s)한편[ ,]",
    "~라는 점에서": r"라는 점에서",
    "주목할 만": r"주목할 만|주목됩니다|주목받",
    "기대를 모으": r"기대를 (?:모으|모아|모았)",
    "관심/시선이 쏠리": r"(?:관심|시선)이 쏠",
    "귀추": r"귀추",
    "행보": r"행보",
    "~를 증명": r"(?:을|를) 증명",
    "화제가 되": r"화제가 (?:되|됐|된)",
    "의미 있는": r"의미 있는|의미가 있",
    "인상적": r"인상적",
    "돋보였": r"돋보였|돋보인",
    "~셈입니다": r"셈(?:입니다|이었|이라)",
    "아쉬움을 남겼": r"아쉬움을 남",
    "눈길을 끌": r"눈길을 (?:끌|끈|끌었)",
    "단연": r"단연",
    "~것으로 보": r"것으로 (?:보|전망|예상)",
    "colon lead-in": r"[가-힣]:\s",
}

_BANNED_RE = {k: re.compile(p, re.MULTILINE) for k, p in BANNED.items()}
_HELD_RE = {k: re.compile(p, re.MULTILINE) for k, p in HELD_OUT.items()}
_LINK_RE = re.compile(r"\]\(https?://[^)]*\)|\(https?://[^)]*\)")
_HEADLINE_RE = re.compile(r"헤드라인[^\n]*\n+\s*\*\*(.+?)\*\*")
_SENTENCE_RE = re.compile(r"[^.!?\n]*[가-힣][^.!?\n]*[.!?]")


def _plain(text: str) -> str:
    return _LINK_RE.sub("]", sections.strip_data_blocks(text or ""))


def monotone_runs(text: str) -> int:
    """Places where three sentences in a row end in the same verb form
    ("…했습니다. …했습니다. …했습니다.")."""
    endings = [s.strip()[-4:] for s in _SENTENCE_RE.findall(text)]
    return sum(1 for a, b, c in zip(endings, endings[1:], endings[2:]) if a == b == c)


def evaluate(text: str) -> Dict:
    plain = _plain(text)
    banned = {k: len(r.findall(plain)) for k, r in _BANNED_RE.items()}
    held = {k: len(r.findall(plain)) for k, r in _HELD_RE.items()}
    headline = _HEADLINE_RE.search(plain)
    return {
        "banned": sum(banned.values()),
        "held_out": sum(held.values()),
        "dashes": banned["long dash"],
        "monotone_runs": monotone_runs(plain),
        "headline_chars": len(headline.group(1)) if headline else None,
        "by_pattern": {k: v for k, v in {**banned, **held}.items() if v},
    }
