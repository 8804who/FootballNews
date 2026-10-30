#!/usr/bin/env python3
"""
harness.py — compare prompt / model variants on the same past editions.

Each run in runs.yml regenerates the chosen editions from the data already
in datas/ (nothing is scraped, uploaded or emailed), then scores them with
the production metrics and pre-send checks, plus tokens, cost and time. The
report puts the runs side by side, with differences from the first run, so
"should we switch to model X?" or "did my prompt change help?" gets a
number instead of a feeling.

    python evaluate/harness.py                            # every run, runs.yml's dates
    python evaluate/harness.py --only baseline,gpt-5.4-nano --dates 20261019
    python evaluate/harness.py --teams Arsenal,Chelsea --judge
    python evaluate/harness.py --rescore --judge          # after a metric change, no regeneration

Output (gitignored): evaluate/runs/{run}/{date}/newsletter_{team}.md and
usage.json, plus evaluate/runs/report.md and report.json.

Generation isn't deterministic, so a difference of a point or two between
runs on 12 editions is noise; look for flags, failed facts and cost.
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Allow running from the project root: python evaluate/harness.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from config import TEAMS
from evaluate import cost, gate, judge
from evaluate.evaluate_main import LABELS, METRICS_VERSION, WEIGHTS, evaluate_newsletter
from evaluate.utils import BASE_DIR, parse_date
from generate_newsletter import generate_edition, write_usage
from summarizers.llm import LLMSummarizer

RUNS_YML = Path(__file__).resolve().parent / "runs.yml"
OUT = Path(__file__).resolve().parent / "runs"


def _yaml(relative: Optional[str], default: str) -> dict:
    return yaml.safe_load((BASE_DIR / (relative or default)).read_text(encoding="utf-8"))


def _generate(run: dict, date_str: str, team: str) -> Dict:
    """One edition for one run. Returns the file, its calls, and any error."""
    summarizer = LLMSummarizer(
        model=run["model"],
        prompt=_yaml(run.get("prompt"), "prompt.yml"),
        examples=_yaml(run.get("examples"), "example.yml"),
        reasoning_effort=run.get("reasoning_effort"),
    )
    path = OUT / run["name"] / date_str / f"newsletter_{team.replace(' ', '_')}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        run_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
        path.write_text(generate_edition(team, run_date, summarizer), encoding="utf-8")
        return {"run": run["name"], "date": date_str, "team": team, "path": path, "calls": summarizer.calls, "error": None}
    except Exception as e:  # one failing model shouldn't stop the others
        return {"run": run["name"], "date": date_str, "team": team, "path": None, "calls": summarizer.calls,
                "error": f"{type(e).__name__}: {str(e)[:160]} (after {time.perf_counter() - started:.0f}s)"}


def _existing(run: dict, date_str: str, team: str) -> Dict:
    """A previous run's output, to re-score after a metric change without
    regenerating (which would cost money and change the outputs)."""
    path = OUT / run["name"] / date_str / f"newsletter_{team.replace(' ', '_')}.md"
    if not path.exists():
        return {"run": run["name"], "date": date_str, "team": team, "path": None, "calls": [],
                "error": "no output to re-score"}
    return {"run": run["name"], "date": date_str, "team": team, "path": path,
            "calls": cost.edition_calls(path), "error": None}


def _score(task: Dict, sources: Dict, use_judge: bool, judge_model: Optional[str]) -> Dict:
    if task["error"]:
        return task
    token = task["path"].stem.replace("newsletter_", "")
    date = parse_date(task["date"])
    task["eval"] = evaluate_newsletter(task["path"], use_judge=use_judge, judge_model=judge_model)
    task["gate"] = gate.check_edition(token, date, task["path"].read_text(encoding="utf-8"), sources[task["date"]])
    return task


def _summarize(tasks: List[Dict]) -> Dict:
    scored = [t for t in tasks if t.get("eval")]
    mean = lambda vals: sum(vals) / len(vals) if vals else None
    return {
        "editions": len(tasks),
        "errors": [f"{t['date']} {t['team']}: {t['error']}" for t in tasks if t["error"]],
        "overall": mean([t["eval"]["overall"] for t in scored if t["eval"]["overall"] is not None]),
        "metrics": {k: mean([t["eval"]["components"][k] for t in scored if t["eval"]["components"][k] is not None])
                    for k in WEIGHTS},
        "flagged": [f"{t['date']} {t['team']}: {'; '.join(t['gate']['problems'])}" for t in scored if t["gate"]["flagged"]],
        "warnings": [f"{t['date']} {t['team']}: {w}" for t in scored for w in t["gate"]["warnings"]],
        "generation": cost.summarize_calls([c for t in tasks for c in t["calls"]]),
        "judge": cost.summarize_calls([c for t in scored for c in t["eval"]["faithfulness"]["calls"]]),
        "per_edition": {f"{t['date']} {t['team']}": t["eval"]["overall"] for t in scored},
    }


def _fmt(v: Optional[float]) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


def _delta(v: Optional[float], base: Optional[float]) -> str:
    if v is None or base is None:
        return _fmt(v)
    d = (v - base) * 100
    return f"{_fmt(v)} ({'+' if d >= 0 else ''}{d:.1f})"


def render_report(runs: List[dict], summaries: Dict[str, Dict], dates: List[str], teams: List[str],
                  use_judge: bool, judge_model: Optional[str]) -> str:
    names = [r["name"] for r in runs]
    base = summaries[names[0]]
    head = "| | " + " | ".join(names) + " |"
    sep = "| --- |" + " --- |" * len(names)
    row = lambda label, cells: f"| {label} | " + " | ".join(cells) + " |"

    lines = [
        f"# Prompt × model comparison — {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        "",
        f"Editions: {', '.join(dates)} × {len(teams)} clubs ({len(dates) * len(teams)} per run) · "
        f"metrics v{METRICS_VERSION} · judge: {'on (' + (judge_model or judge.DEFAULT_MODEL) + ', 3 votes)' if use_judge else 'off'}. "
        f"Differences are from `{names[0]}`, in points.",
        "",
        head, sep,
        row("Model", [r["model"] + (f" (reasoning {r['reasoning_effort']})" if r.get("reasoning_effort") else "") for r in runs]),
        row("**Overall**", [f"**{_delta(summaries[n]['overall'], base['overall'])}**" for n in names]),
    ]
    lines += [row(LABELS[k], [_delta(summaries[n]["metrics"][k], base["metrics"][k]) for n in names]) for k in WEIGHTS]
    gen = lambda n: summaries[n]["generation"]
    lines += [
        row("Flagged by the edition checks", [f"{len(summaries[n]['flagged'])} / {summaries[n]['editions']}" for n in names]),
        row("Pre-send warnings", [str(len(summaries[n]["warnings"])) for n in names]),
        row("Errors", [str(len(summaries[n]["errors"])) for n in names]),
        row("Generation cost", [("unpriced" if gen(n)["cost_usd"] is None else f"${gen(n)['cost_usd']:.3f}") for n in names]),
        row("Cost per edition", [("—" if gen(n)["cost_usd"] is None or not summaries[n]["editions"]
                                  else f"${gen(n)['cost_usd'] / summaries[n]['editions']:.4f}") for n in names]),
        row("Tokens in / out (reasoning)", [f"{gen(n)['input_tokens']:,} / {gen(n)['output_tokens']:,} ({gen(n)['reasoning_tokens']:,})" for n in names]),
        row("Seconds per call", [f"{gen(n)['seconds'] / gen(n)['calls']:.1f}" if gen(n)["calls"] else "—" for n in names]),
        "",
        "## Overall per edition",
        "",
        "| Edition | " + " | ".join(names) + " |",
        "| --- |" + " --- |" * len(names),
    ]
    for key in sorted({k for n in names for k in summaries[n]["per_edition"]}):
        lines.append(f"| {key} | " + " | ".join(_fmt(summaries[n]["per_edition"].get(key)) for n in names) + " |")

    lines += ["", "## What the checks found", ""]
    for n in names:
        s = summaries[n]
        found = [f"- ⛔ flagged — {h}" for h in s["flagged"]] + [f"- ⚠ {w}" for w in s["warnings"]] + [f"- ✗ error — {e}" for e in s["errors"]]
        lines += [f"### {n}", ""] + (found or ["- nothing"]) + [""]
    lines += [f"Outputs: `evaluate/runs/<run>/<date>/newsletter_<team>.md`. Judge cost per run: "
              + ", ".join(f"{n} ${summaries[n]['judge']['cost_usd'] or 0:.3f}" for n in names) + "."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare prompt / model variants on past editions.")
    parser.add_argument("--config", default=str(RUNS_YML), help="Runs file (default evaluate/runs.yml)")
    parser.add_argument("--only", help="Comma-separated run names to include")
    parser.add_argument("--dates", help="Comma-separated edition dates (default: the config's)")
    parser.add_argument("--teams", help="Comma-separated teams (default: setting.yml's)")
    parser.add_argument("--judge", action="store_true", help="Also run the LLM faithfulness judge")
    parser.add_argument("--judge-model", help=f"Judge model (default {judge.DEFAULT_MODEL})")
    parser.add_argument("--workers", type=int, default=8, help="Parallel API calls (default 8)")
    parser.add_argument("--rescore", action="store_true",
                        help="Re-score the outputs already in evaluate/runs/ instead of regenerating")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    runs = [r for r in config["runs"] if not args.only or r["name"] in args.only.split(",")]
    dates = args.dates.split(",") if args.dates else [str(d) for d in config["dates"]]
    teams = args.teams.split(",") if args.teams else [t["name"] for t in TEAMS]
    print(f"{len(runs)} run(s) × {len(dates)} date(s) × {len(teams)} club(s)")

    jobs = [(r, d, t) for r in runs for d in dates for t in teams]
    if args.rescore:
        tasks = [_existing(*job) for job in jobs]
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            tasks = list(pool.map(lambda job: _generate(*job), jobs))
        for run in runs:
            for d in dates:
                usage = {t["team"]: t["calls"] for t in tasks if t["run"] == run["name"] and t["date"] == d and not t["error"]}
                if usage:
                    write_usage(str(OUT / run["name"] / d), run["model"], usage)
        print("generated; scoring…")

    sources = {d: {t.replace(" ", "_"): gate.club_sources(t.replace(" ", "_"), parse_date(d)) for t in teams} for d in dates}
    with ThreadPoolExecutor(max_workers=args.workers if args.judge else 1) as pool:
        tasks = list(pool.map(lambda t: _score(t, sources, args.judge, args.judge_model), tasks))

    summaries = {r["name"]: _summarize([t for t in tasks if t["run"] == r["name"]]) for r in runs}
    report = render_report(runs, summaries, dates, teams, args.judge, args.judge_model)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.md").write_text(report, encoding="utf-8")
    (OUT / "report.json").write_text(json.dumps({"runs": runs, "dates": dates, "summaries": summaries}, indent=2, default=str),
                                     encoding="utf-8")
    print(report)
    print(f"Report: {OUT / 'report.md'}")


if __name__ == "__main__":
    main()
