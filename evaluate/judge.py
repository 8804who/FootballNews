"""
Metric 8 — Faithfulness (LLM judge, optional)
The other metrics check names, numbers and links. None of them can tell
that "Gyokeres keen to leave Arsenal" came out as "Arsenal 이적을 원한다"
(wants to join), or that a scoreboard one-liner says Chelsea "couldn't hold
on" after they won. This asks a model, item by item, whether the newsletter
says what its source says: the match story and each scoreboard row against
the match data, and each news item against the headline(s) it links to.

Optional (evaluate_main.py --judge), because it costs a call per edition and
isn't fully deterministic — which is also why it stays out of the pre-send
gate.

Result keys
-----------
score         : float | None — SUPPORTED / judged items
judged        : int
contradicted  : list[str]    — "item excerpt — reason"
unsupported   : list[str]
calls         : list[dict]   — usage records (tokens, time) for the cost report
"""

import re
import time
from collections import Counter
from typing import Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, Field

from evaluate.news_grounding import extract_news_section, split_news_items
from evaluate.utils import extract_links, strip_links

# Chosen on six known cases (a reversed result, a reversed headline, a leaked
# rumor, three correct items), each run twice with a 3-vote majority:
# gpt-5-mini 6/6 both times; gpt-5.4-mini (no reasoning by default) 5/6 both
# times. It is also the model that writes the newsletter, so it may share its
# blind spots — keep it fixed when comparing generator models in harness.py.
DEFAULT_MODEL = "gpt-5-mini"

_INSTRUCTIONS = """You fact-check a Korean football newsletter. Each numbered ITEM is Korean text from the newsletter; its SOURCE is what it was written from (English headlines, or the MATCH DATA). Judge facts only, not style or tone.

- SUPPORTED: every factual claim in the item is in its source. Paraphrase, translation, and light commentary or opinion ("a big moment for the club") are fine.
- CONTRADICTED: the item states something its source contradicts: the wrong result or winner, the wrong player, or the reverse of what a headline says (e.g. "wants to join" when the headline says "wants to leave").
- UNSUPPORTED: the item states a specific fact its source doesn't contain: a person, number, date, quote or event that isn't there.

Give a verdict for every item, with one short reason in English."""


class Verdict(BaseModel):
    id: int = Field(description="The item number")
    verdict: Literal["SUPPORTED", "CONTRADICTED", "UNSUPPORTED"]
    reason: str = Field(description="One short sentence in English")


class Verdicts(BaseModel):
    verdicts: List[Verdict]


_STORY_RE = re.compile(r"^##[^\n]*베스트\s*경기[^\n]*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
_ROW_RE = re.compile(r"^\|(.+\svs\s.+)\|\s*$", re.MULTILINE | re.IGNORECASE)


def build_items(newsletter_text: str, matches_text: str, headline_by_url: Mapping[str, str]) -> List[dict]:
    """The story, each scoreboard row and each linked news item, with sources."""
    items = []
    if matches_text:
        story = _STORY_RE.search(newsletter_text)
        if story and story.group(1).strip():
            items.append({"kind": "story", "text": story.group(1).strip(), "source": None})
        for row in _ROW_RE.findall(newsletter_text):
            items.append({"kind": "scoreboard", "text": f"|{row}|", "source": None})
    for item in split_news_items(extract_news_section(newsletter_text)):
        headlines = [headline_by_url[url] for _, url in extract_links(item) if url in headline_by_url]
        if headlines:
            items.append({"kind": "news", "text": strip_links(item), "source": "\n".join(headlines)})
    return items


def _prompt(items: List[dict], matches_text: str) -> str:
    parts = [f"MATCH DATA (the source for story and scoreboard items):\n{matches_text}"] if matches_text else []
    for i, item in enumerate(items, 1):
        source = item["source"] or "MATCH DATA"
        parts.append(f"ITEM {i} ({item['kind']})\n{item['text']}\nSOURCE {i}\n{source}")
    return "\n\n".join(parts)


def _ask(model: str, messages: list):
    from langchain_openai import ChatOpenAI

    from config import API_KEY
    from summarizers.llm import usage_record

    llm = ChatOpenAI(model=model, temperature=0, api_key=API_KEY["OPENAI"])
    started = time.perf_counter()
    result = llm.with_structured_output(Verdicts, include_raw=True).invoke(messages)
    verdicts = {v.id: v for v in (result["parsed"].verdicts if result["parsed"] else [])}
    return verdicts, usage_record("judge", model, result["raw"], time.perf_counter() - started)


def evaluate(newsletter_text: str, matches_text: str, headline_by_url: Mapping[str, str],
             model: Optional[str] = None, samples: int = 3) -> Dict:
    """
    Args:
        newsletter_text: full text of the newsletter file, links included
        matches_text:    this edition's match data (edition.matches_markdown)
        headline_by_url: {headline URL: headline} for this edition's news
        model:           judge model (DEFAULT_MODEL if None)
        samples:         independent judgements per item; the majority wins.
                         One sample flipped verdicts between identical runs
                         in calibration, three made them stable.
    """
    items = build_items(newsletter_text, matches_text, headline_by_url)
    if not items:
        return {"score": None, "judged": 0, "contradicted": [], "unsupported": [], "calls": []}

    from concurrent.futures import ThreadPoolExecutor

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = [SystemMessage(_INSTRUCTIONS), HumanMessage(_prompt(items, matches_text))]
    with ThreadPoolExecutor(max_workers=samples) as pool:
        runs = list(pool.map(lambda _: _ask(model or DEFAULT_MODEL, messages), range(samples)))
    calls = [call for _, call in runs]

    judged = []
    for i, item in enumerate(items, 1):
        votes = [verdicts[i] for verdicts, _ in runs if i in verdicts]
        if votes:
            winner = Counter(v.verdict for v in votes).most_common(1)[0][0]
            judged.append((item, next(v for v in votes if v.verdict == winner)))
    label = lambda item, v: f"[{item['kind']}] {item['text'][:80]} — {v.reason}"
    return {
        "score": sum(v.verdict == "SUPPORTED" for _, v in judged) / len(judged) if judged else None,
        "judged": len(judged),
        "contradicted": [label(it, v) for it, v in judged if v.verdict == "CONTRADICTED"],
        "unsupported": [label(it, v) for it, v in judged if v.verdict == "UNSUPPORTED"],
        "calls": calls,
    }
