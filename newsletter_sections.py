"""Section headings of a newsletter, in one place.

prompt.yml and example.yml spell the LLM's headings out for the model; the
code here (gate checks, evaluation, the blocks summarizers/blocks.py renders)
uses these constants so a rename can't silently break one of them.
"""

import re

# Written by the LLM
NEWS = "## 🔁 이적 & 뉴스"
CONFIRMED = "### ✅ 확정 소식"
RUMOR = "### 🧪 루머"
DRAMA = "### 🎭 드라마 앵글"
QUIET = "## 🌙 이번 주 휴식"

# Keywords (regex fragments) of the LLM's match headings, e.g.
# "## 🏆 이번 주 헤드라인"; the emoji and wording around them may vary.
HEADLINE = "헤드라인"
MATCH_OF_WEEK = r"베스트\s*경기"
SCOREBOARD = "스코어보드"

# Older editions' news sub-headings (before 2026-11), still read by the gate.
LEGACY_CONFIRMED = "### ✅ 공식 뉴스"
LEGACY_RUMOR = "### 🧪 루머 밀"

# Rendered by code from FotMob data (summarizers/blocks.py), never by the LLM
STANDINGS_AND_FIXTURES = "## 📍 순위 & 다음 경기"
STANDINGS = "## 📍 현재 순위"
FIXTURES = "## 📅 다음 경기"
INJURIES = "## 🏥 결장 예상"
DATA_BLOCKS = (STANDINGS_AND_FIXTURES, STANDINGS, FIXTURES, INJURIES)

# A confirmed item taken from FotMob's transfer list has no link to give.
FOTMOB_LABEL = "(FotMob 공식)"

_DATA_BLOCK_RE = re.compile(
    r"^(?:" + "|".join(re.escape(h) for h in DATA_BLOCKS) + r")[ \t]*\n.*?(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def strip_data_blocks(text: str) -> str:
    """The newsletter without its code-rendered blocks. They are copied from
    FotMob by code, so the metrics and checks score only what the LLM wrote."""
    return _DATA_BLOCK_RE.sub("", text)


# The news heading as the metrics find it (older editions vary its wording).
NEWS_HEADING_RE = re.compile(r"^##\s.*(이적|뉴스)", re.MULTILINE)
# The headline's bold title line.
HEADLINE_TITLE_RE = re.compile(HEADLINE + r"[^\n]*\n+\s*\*\*(.+?)\*\*")


def section_re(*keywords: str) -> "re.Pattern[str]":
    """Matches each `## ` section whose heading contains one of `keywords`;
    group 1 is its body, up to the next `## ` heading."""
    return re.compile(r"^##[^\n]*(?:" + "|".join(keywords) + r")[^\n]*\n(.*?)(?=^## |\Z)",
                      re.MULTILINE | re.DOTALL)
