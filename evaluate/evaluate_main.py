#!/usr/bin/env python3
"""
evaluate_main.py — Football News AI Evaluation Orchestrator

Runs the evaluation metrics against every newsletter in datas/newsletter/
and prints a quantified report with per-newsletter details and an aggregate
summary.

Metrics (version 2, 2026-10-30)
-------------------------------
1. Score Accuracy       (20%) — scoreboard vs. fotmob source (club aliases understood)
2. Match Facts          (15%) — "minute + player" claims vs. match events
3. News Grounding       (15%) — each news item vs. the headline(s) it links to
4. No Hallucination     (15%) — names that appear in no source
5. Section Completeness (10%) — the sections this week's source calls for
6. Language Compliance  (10%) — Korean, apart from the English names the style guide requires
7. No LLM Drift          (5%) — model went off-script (chatbot mode)
8. Faithfulness         (10%) — LLM judge: does each item say what its source says (--judge)

A metric that can't be measured for an edition (no claims to check, judge
off, ...) is left out and the remaining weights renormalized, rather than
scored as pass or fail. Generation tokens and cost come from usage.json.

The metrics measure faithfulness to the source the model was given. If
collection missed matches, an edition can score 100% and still leave out the
weekend, so coverage (collected ÷ finished matches on FotMob's fixture list)
is reported beside the score, not inside it; evaluate/gate.py flags such
editions on the dashboard.

Usage
-----
    python evaluate/evaluate_main.py
    python evaluate/evaluate_main.py --date 20260306
    python evaluate/evaluate_main.py --team Liverpool
    python evaluate/evaluate_main.py --date 20261102 --judge \
        --output datas/evaluation/20261102/report.md \
        --json-output datas/evaluation/20261102/summary.json
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Allow running from the project root: python evaluate/evaluate_main.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import edition
from evaluate import (
    cost,
    hallucination,
    judge,
    language_compliance,
    llm_drift,
    match_facts,
    news_grounding,
    score_accuracy,
    section_completeness,
)
from evaluate import utils
from evaluate.utils import (
    NEWSLETTER_ROOT,
    load_fotmob_for_team,
    load_match_blocks,
    load_news_items_for_team,
    load_transfer_lines,
    parse_date,
    resolve_newsletter_token,
    source_available,
    strip_links,
)

# Bump when a metric's definition or weight changes: stored summaries and the
# dashboard trend only compare scores from the same version.
METRICS_VERSION = 2

WEIGHTS = {
    "score_accuracy":       0.20,
    "match_facts":          0.15,
    "news_grounding":       0.15,
    "no_hallucination":     0.15,
    "section_completeness": 0.10,
    "language_compliance":  0.10,
    "no_drift":             0.05,
    "faithfulness":         0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "WEIGHTS must sum to 1.0"

LABELS = {
    "score_accuracy":       "Score Accuracy",
    "match_facts":          "Match Facts",
    "news_grounding":       "News Grounding",
    "no_hallucination":     "No Hallucination",
    "section_completeness": "Section Completeness",
    "language_compliance":  "Language Compliance",
    "no_drift":             "No LLM Drift",
    "faithfulness":         "Faithfulness (judge)",
}

_NO_JUDGE = {"score": None, "judged": 0, "contradicted": [], "unsupported": [], "calls": []}


# ─────────────────────────── per-newsletter evaluation ──────────────────────

def evaluate_newsletter(newsletter_file: Path, use_judge: bool = False,
                        judge_model: Optional[str] = None) -> Optional[Dict]:
    """Run all metrics for one newsletter file. Returns None when none of its
    source data is available (a news-only or quiet week is still evaluated)."""
    date_str = newsletter_file.parent.name
    nl_date = parse_date(date_str)
    if nl_date is None:
        return None

    token = resolve_newsletter_token(newsletter_file.stem)
    if token is None or not source_available(token, nl_date):
        return None

    raw = newsletter_file.read_text(encoding="utf-8")
    # Source links ("([BBC](https://…))") are scored as their label only, so
    # URL fragments aren't mistaken for names or English text.
    text = strip_links(raw)

    start, end = edition.edition_window(nl_date)
    blocks = load_match_blocks(token, nl_date)
    fotmob_matches, source_players = load_fotmob_for_team(token, nl_date)
    news_items = load_news_items_for_team(token, nl_date)
    transfers = load_transfer_lines(token, nl_date)

    # Run each metric
    m1 = score_accuracy.evaluate(fotmob_matches, text)
    m3 = llm_drift.evaluate(text)                          # drift needed by m2
    m2 = section_completeness.evaluate(
        text, m3["detected"], has_matches=bool(fotmob_matches), has_news=bool(news_items or transfers))
    # The newsletter also covers RSS/transfer news, so names from those
    # sources are legitimate — fold them into the pool or they'd be flagged.
    news_words = news_grounding.build_source_words(
        "\n".join([item.headline for item in news_items] + transfers), source_players)
    m4 = hallucination.evaluate(text, source_players | news_words)
    m5 = language_compliance.evaluate(raw)
    headline_words = {item.link: news_grounding.build_source_words(item.headline, set()) for item in news_items}
    m6 = news_grounding.evaluate(raw, news_words, headline_words)
    m7 = match_facts.evaluate(text, blocks)
    m8 = judge.evaluate(
        raw, edition.matches_markdown(token.replace("_", " "), blocks, start, end),
        {item.link: item.headline for item in news_items}, model=judge_model,
    ) if use_judge else _NO_JUDGE

    # Overall weighted score. A component is None when that metric genuinely
    # couldn't be measured (e.g. no source players to check hallucination
    # against) — treating an unmeasured metric as a perfect (or zero) score
    # would silently mask the gap, so instead we exclude it and renormalize
    # the weights over whatever *was* measured.
    components: Dict[str, Optional[float]] = {
        "score_accuracy":       m1["score"],
        "match_facts":          m7["score"],
        "news_grounding":       m6["score"],
        "no_hallucination":     (1.0 - m4["rate"]) if m4["rate"] is not None else None,
        "section_completeness": m2["score"],
        "language_compliance":  m5["ratio"],
        "no_drift":             0.0 if m3["detected"] else 1.0,
        "faithfulness":         m8["score"],
    }
    assert set(components) == set(WEIGHTS), "components/WEIGHTS key mismatch"
    measured = {k: v for k, v in components.items() if v is not None}
    weight_sum = sum(WEIGHTS[k] for k in measured)
    overall = (
        sum(WEIGHTS[k] * v for k, v in measured.items()) / weight_sum
        if weight_sum > 0 else None
    )
    generation_calls = cost.edition_calls(newsletter_file)
    finished, uncollected = edition.uncollected_fixtures(
        edition.load_fixtures(token, start, nl_date, root=utils.DATA_ROOT), blocks, start, end)

    return {
        "date":    date_str,
        "team":    token.replace("_", " "),
        # raw metric results
        "score_accuracy":       m1,
        "section_completeness": m2,
        "llm_drift":            m3,
        "hallucination":        m4,
        "language_compliance":  m5,
        "news_grounding":       m6,
        "match_facts":          m7,
        "faithfulness":         m8,
        # scalars for aggregation
        "components":           components,
        "overall":              overall,
        # None before collect_news saved FotMob's fixture list (Oct 30 2026)
        "coverage":             (finished - len(uncollected)) / finished if finished else None,
        "uncollected":          [f"{f.get('home')} {f.get('score')} {f.get('away')}" for f in uncollected],
        "calls":                generation_calls,
        "usage":                cost.summarize_calls(generation_calls),
        "judge_usage":          cost.summarize_calls(m8["calls"]),
    }


# ─────────────────────────── report ─────────────────────────────────────────

def _pct(v: Optional[float]) -> str:
    return "N/A" if v is None else f"{v * 100:.1f}%"


def _usage_line(usage: Dict) -> str:
    if not usage["calls"]:
        return "not recorded"
    dollars = "unpriced" if usage["cost_usd"] is None else f"${usage['cost_usd']:.4f}"
    return (f"{usage['calls']} calls · {usage['input_tokens']:,} in / {usage['output_tokens']:,} out tokens "
            f"({usage['reasoning_tokens']:,} reasoning) · {usage['seconds']}s · {dollars}")


def _metric_rows(r: Dict) -> List[str]:
    m1, m2, m3, m4 = r["score_accuracy"], r["section_completeness"], r["llm_drift"], r["hallucination"]
    m5, m6, m7, m8 = r["language_compliance"], r["news_grounding"], r["match_facts"], r["faithfulness"]
    detail = {
        "score_accuracy":       f"{len(m1['details'])} matches",
        "match_facts":          f"{m7['checked']} claims checked",
        "news_grounding":       f"{len(m6['items'])} items checked",
        "no_hallucination":     f"{m4['total_names']} names checked",
        "section_completeness": ", ".join(f"{'✓' if ok else '✗'} {name}" for name, ok in m2["hits"].items()),
        "language_compliance":  f"{'✓' if m5['passed'] else '✗'} target {m5['target']:.0%}",
        "no_drift":             "⚠ drift: " + ", ".join(m3["signals"][:2]) if m3["detected"] else "✓",
        "faithfulness":         f"{m8['judged']} items judged" if m8["judged"] else "judge off",
    }
    return [f"| {LABELS[k]} | {_pct(r['components'][k])} | {detail[k]} |" for k in WEIGHTS]


def _problem_lines(r: Dict) -> List[str]:
    m1, m4, m6, m7, m8 = (r["score_accuracy"], r["hallucination"], r["news_grounding"],
                          r["match_facts"], r["faithfulness"])
    lines = [f"- ✗ never collected (not in the source at all): {match}" for match in r["uncollected"]]
    lines += [f"- ✗ score: {m[0]} vs {m[1]} {m[2]}-{m[3]} not on the scoreboard correctly"
              for m, ok in m1["details"] if not ok]
    lines += [f"- ✗ not in this week's source: {row[0]} vs {row[1]} {row[2]}-{row[3]}" for row in m1["extra_rows"]]
    lines += [f"- ✗ match fact: {f}" for f in m7["failed"]]
    lines += [f"- ✗ ungrounded news item: {item[:90]}" for item in m6["ungrounded"]]
    if m4["hallucinated_names"]:
        lines.append(f"- ✗ names in no source: {', '.join(sorted(m4['hallucinated_names']))}")
    lines += [f"- ✗ judge — contradicted: {c}" for c in m8["contradicted"]]
    lines += [f"- ✗ judge — unsupported: {u}" for u in m8["unsupported"]]
    return lines


def _mean(results: List[Dict], key: str) -> Optional[float]:
    vals = [r["components"][key] for r in results if r["components"][key] is not None]
    return sum(vals) / len(vals) if vals else None


def render_report_markdown(results: List[Dict], judged: bool = False) -> str:
    """The evaluation report as a markdown document (also what's printed)."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    weights = ", ".join(f"{LABELS[k].split(' (')[0].lower()} {w:.0%}" for k, w in WEIGHTS.items())
    lines: List[str] = [
        "# Football News — AI Evaluation Report",
        "",
        f"_Generated: {generated_at} · metrics v{METRICS_VERSION} · judge {'on' if judged else 'off'}_",
        "",
        f"Overall = weighted mean of the measured metrics ({weights}).",
        "",
    ]
    if not results:
        lines.append("No evaluatable newsletters found.")
        return "\n".join(lines) + "\n"

    for r in results:
        lines += [f"## [{r['date']}] {r['team']}", "", "| Metric | Score | Detail |", "| --- | --- | --- |"]
        lines += _metric_rows(r)
        lines.append(f"| **Overall** | **{_pct(r['overall'])}** | weighted |")
        lines += [
            "",
            f"Coverage: {_pct(r['coverage'])} of FotMob's finished matches were collected"
            if r["coverage"] is not None else "Coverage: no FotMob fixture list for this week",
            "",
            f"Generation: {_usage_line(r['usage'])}",
            "",
        ]
        problems = _problem_lines(r)
        if problems:
            lines += problems + [""]

    generation = cost.summarize_calls([c for r in results for c in r["calls"]])
    judging = cost.summarize_calls([c for r in results for c in r["faithfulness"]["calls"]])
    lines += [f"## Aggregate (n={len(results)})", "", "| Metric | Mean |", "| --- | --- |"]
    lines += [f"| {LABELS[k]} | {_pct(_mean(results, k))} |" for k in WEIGHTS]
    overall_vals = [r["overall"] for r in results if r["overall"] is not None]
    overall = sum(overall_vals) / len(overall_vals) if overall_vals else None
    coverage = [r["coverage"] for r in results if r["coverage"] is not None]
    lines += [
        f"| **Overall** | **{_pct(overall)}** |",
        "",
        f"Coverage: {_pct(sum(coverage) / len(coverage)) if coverage else 'no fixture lists'}",
        "",
        f"Generation: {_usage_line(generation)}",
        "",
        f"Judge: {_usage_line(judging)}",
    ]
    return "\n".join(lines) + "\n"


def render_report_json(results: List[Dict], judged: bool = False) -> Dict:
    """Machine-readable summary, stored per week as summary.json. The
    dashboard reads it instead of re-scoring the week with whatever metric
    code happens to be current."""
    if not results:
        return {"metrics_version": METRICS_VERSION, "date": None, "n": 0, "overall_score": None, "metrics": {}}

    def pct(v: Optional[float]) -> Optional[float]:
        return round(v * 100, 1) if v is not None else None

    overall_vals = [r["overall"] for r in results if r["overall"] is not None]
    coverage = [r["coverage"] for r in results if r["coverage"] is not None]
    return {
        "metrics_version": METRICS_VERSION,
        "date": max(r["date"] for r in results),
        "n": len(results),
        "judge": judged,
        "overall_score": pct(sum(overall_vals) / len(overall_vals)) if overall_vals else None,
        "metrics": {k: pct(_mean(results, k)) for k in WEIGHTS},
        "coverage": pct(sum(coverage) / len(coverage)) if coverage else None,
        "usage": {
            "generation": cost.summarize_calls([c for r in results for c in r["calls"]]),
            "judge": cost.summarize_calls([c for r in results for c in r["faithfulness"]["calls"]]),
        },
        "teams": [
            {
                "team": r["team"],
                "date": r["date"],
                "overall": pct(r["overall"]),
                "metrics": {k: pct(v) for k, v in r["components"].items()},
                "coverage": pct(r["coverage"]),
                "cost_usd": r["usage"]["cost_usd"],
            }
            for r in results
        ],
    }


# ─────────────────────────── entry point ────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run all Football News AI evaluations and print a report."
    )
    parser.add_argument("--date", help="Evaluate only this date (YYYYMMDD)")
    parser.add_argument("--team", help="Evaluate only this team (partial match)")
    parser.add_argument(
        "--output",
        help="Write the report as markdown to this file path, in addition to printing it",
    )
    parser.add_argument(
        "--json-output",
        help="Write the summary as JSON to this file path (summary.json, read by the dashboard)",
    )
    parser.add_argument("--judge", action="store_true",
                        help="Also run the LLM faithfulness judge (one 3-vote call per edition)")
    parser.add_argument("--judge-model", help=f"Judge model (default {judge.DEFAULT_MODEL})")
    args = parser.parse_args()

    files: List[Path] = []
    if NEWSLETTER_ROOT.exists():
        for date_dir in sorted(NEWSLETTER_ROOT.iterdir()):
            if not date_dir.is_dir():
                continue
            if args.date and date_dir.name != args.date:
                continue
            for nf in sorted(date_dir.glob("newsletter_*.md")):
                if args.team and args.team.lower().replace(" ", "_") not in nf.stem.lower():
                    continue
                files.append(nf)

    # Editions are independent; with the judge on, each waits ~40s on the API.
    with ThreadPoolExecutor(max_workers=6 if args.judge else 1) as pool:
        evaluated = pool.map(lambda nf: evaluate_newsletter(nf, use_judge=args.judge, judge_model=args.judge_model), files)
        results: List[Dict] = [r for r in evaluated if r is not None]

    report = render_report_markdown(results, judged=args.judge)
    print(report)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"Markdown report written to: {out_path}")

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(render_report_json(results, judged=args.judge), indent=2), encoding="utf-8")
        print(f"JSON summary written to: {json_path}")


if __name__ == "__main__":
    main()
