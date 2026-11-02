#!/usr/bin/env python3
"""
pairwise.py — blind A/B comparison of two harness runs, by an LLM and by you.

Style isn't a defect the metrics can score, so this asks, for each edition
both runs generated, which version reads more like a Korean sports editor
wrote it ("natural") and which a casual fan would rather read or forward
("fun"). Each pair is judged twice with A and B swapped; a run wins only
when both orders agree, so position bias can't decide the result.

It also writes the same pairs as blind files for a human read, which
should be the deciding vote: evaluate/runs/blind/{date}_{team}.md, with the
answer key in key.json.

    python evaluate/pairwise.py before after          # runs under evaluate/runs/
    python evaluate/pairwise.py before after --no-llm # only write the blind files
"""

import argparse
import json
import random
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import newsletter_sections as sections
from evaluate import judge
from evaluate.utils import strip_links

RUNS = Path(__file__).resolve().parent / "runs"

_INSTRUCTIONS = """You compare two versions of the same weekly Korean football newsletter, written from the same data. Ignore which facts are included; judge only the writing.

natural: which version reads more like a skilled Korean sports editor wrote it, and less like machine-generated Korean (stock phrases, translationese, hedging, long dashes, generic filler)?
fun: which version would a casual Korean fan rather read and forward to a friend?

Answer each with "A", "B" or "tie", and give a one-sentence reason in English."""


class Verdict(BaseModel):
    natural: Literal["A", "B", "tie"]
    fun: Literal["A", "B", "tie"]
    reason: str


def _readable(path: Path) -> str:
    """The edition as a reader sees it, minus the masthead (identical in both)
    and the code-rendered blocks (not the model's writing)."""
    text = strip_links(sections.strip_data_blocks(path.read_text(encoding="utf-8")))
    return re.sub(r"^# .*\n+", "", text).strip()


def _ask(model: str, a: str, b: str) -> Verdict:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI

    from config import API_KEY

    llm = ChatOpenAI(model=model, temperature=0, api_key=API_KEY["OPENAI"]).with_structured_output(Verdict)
    return llm.invoke([SystemMessage(_INSTRUCTIONS), HumanMessage(f"=== VERSION A ===\n{a}\n\n=== VERSION B ===\n{b}")])


def _consistent(first: str, swapped: str) -> str:
    """'x' / 'y' when both orders agree (x was A first, B second), else 'tie'."""
    if first == "A" and swapped == "B":
        return "x"
    if first == "B" and swapped == "A":
        return "y"
    return "tie"


def compare(run_x: str, run_y: str, model: str, use_llm: bool = True, seed: int = 7) -> dict:
    pairs = []
    for x_file in sorted((RUNS / run_x).glob("*/newsletter_*.md")):
        y_file = RUNS / run_y / x_file.parent.name / x_file.name
        if y_file.exists():
            pairs.append((x_file.parent.name, x_file.stem.replace("newsletter_", ""), _readable(x_file), _readable(y_file)))

    blind = RUNS / "blind"
    blind.mkdir(parents=True, exist_ok=True)
    rng, key = random.Random(seed), {}
    for date, team, x, y in pairs:
        x_is_a = rng.random() < 0.5
        a, b = (x, y) if x_is_a else (y, x)
        key[f"{date}_{team}"] = {"A": run_x if x_is_a else run_y, "B": run_y if x_is_a else run_x}
        (blind / f"{date}_{team}.md").write_text(
            f"# {date} · {team.replace('_', ' ')}\n\n어느 쪽이 더 사람이 쓴 것처럼 자연스럽고, 친구에게 보내고 싶나요?\n\n"
            f"---\n\n## A\n\n{a}\n\n---\n\n## B\n\n{b}\n", encoding="utf-8")
    (blind / "key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")

    result = {"pairs": len(pairs), "x": run_x, "y": run_y, "model": model, "natural": {}, "fun": {}, "details": []}
    if not use_llm:
        return result

    def judge_pair(pair):
        date, team, x, y = pair
        first, swapped = _ask(model, x, y), _ask(model, y, x)
        return date, team, first, swapped

    with ThreadPoolExecutor(max_workers=6) as pool:
        judged = list(pool.map(judge_pair, pairs))
    for axis in ("natural", "fun"):
        counts = Counter(_consistent(getattr(f, axis), getattr(s, axis)) for _, _, f, s in judged)
        result[axis] = {run_x: counts["x"], run_y: counts["y"], "inconsistent or tie": counts["tie"]}
    result["details"] = [{"edition": f"{d} {t}", "natural": [f.natural, s.natural], "fun": [f.fun, s.fun],
                          "reason": f.reason} for d, t, f, s in judged]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Blind A/B comparison of two harness runs.")
    parser.add_argument("run_x")
    parser.add_argument("run_y")
    parser.add_argument("--model", default=judge.DEFAULT_MODEL)
    parser.add_argument("--no-llm", action="store_true", help="Only write the blind files for a human read")
    args = parser.parse_args()
    result = compare(args.run_x, args.run_y, args.model, use_llm=not args.no_llm)
    (RUNS / f"pairwise_{args.run_x}_vs_{args.run_y}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                                                      encoding="utf-8")
    print(f"{result['pairs']} pairs, each judged in both orders by {result['model']}")
    for axis in ("natural", "fun"):
        print(f"  {axis}: {result[axis]}")
    print(f"Blind files for your own read: {RUNS / 'blind'} (answer key: key.json)")


if __name__ == "__main__":
    main()
