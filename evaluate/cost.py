"""Token usage → USD, using evaluate/pricing.yml.

generate_newsletter.py and the harness record every LLM call in usage.json
(summarizers.llm.usage_record); this turns those records into totals and a
cost per edition.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import yaml

PRICING_YML = Path(__file__).resolve().parent / "pricing.yml"


@lru_cache(maxsize=None)
def prices() -> Dict[str, dict]:
    return (yaml.safe_load(PRICING_YML.read_text(encoding="utf-8")) or {}).get("models", {})


def call_cost(call: dict) -> Optional[float]:
    """USD for one call, or None if its model has no price in pricing.yml."""
    price = prices().get(call.get("model"))
    if not price:
        return None
    cached = call.get("cached_input_tokens", 0)
    fresh = call.get("input_tokens", 0) - cached
    return (
        fresh * price["input"]
        + cached * price.get("cached_input", price["input"])
        + call.get("output_tokens", 0) * price["output"]
    ) / 1_000_000


def summarize_calls(calls: List[dict]) -> Dict:
    """Totals over a list of calls. cost_usd is None if any call is unpriced."""
    costs = [call_cost(c) for c in calls]
    return {
        "calls": len(calls),
        "input_tokens": sum(c.get("input_tokens", 0) for c in calls),
        "output_tokens": sum(c.get("output_tokens", 0) for c in calls),
        "reasoning_tokens": sum(c.get("reasoning_tokens", 0) for c in calls),
        "seconds": round(sum(c.get("seconds", 0) for c in calls), 1),
        "cost_usd": round(sum(costs), 4) if calls and None not in costs else None,
    }


def edition_calls(newsletter_file: Path) -> List[dict]:
    """The generation calls recorded for this newsletter's team (usage.json
    next to it), or [] for editions generated before usage was recorded."""
    usage_path = newsletter_file.parent / "usage.json"
    if not usage_path.exists():
        return []
    team = newsletter_file.stem.replace("newsletter_", "").replace("_", " ")
    return json.loads(usage_path.read_text(encoding="utf-8")).get("teams", {}).get(team, [])
