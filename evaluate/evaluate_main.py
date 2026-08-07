#!/usr/bin/env python3
"""
evaluate_main.py — Football News AI Evaluation Orchestrator

Runs all five evaluation metrics against every newsletter in datas/newsletter/
and prints a quantified report with per-newsletter details and an aggregate
summary.

Metrics
-------
1. Score Accuracy       (weight 30%) — newsletter scores vs. fotmob source
2. Section Completeness (weight 20%) — 4 required sections present & valid
3. LLM Drift            (weight 15%) — model went off-script (chatbot mode)
4. Hallucination Rate   (weight 25%) — player names not found in source
5. Language Compliance  (weight 10%) — Korean character ratio (target >80%)

Usage
-----
    python evaluate/evaluate_main.py
    python evaluate/evaluate_main.py --date 20260306
    python evaluate/evaluate_main.py --team Liverpool
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# Allow running from the project root: python evaluate/evaluate_main.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluate import (
    hallucination,
    language_compliance,
    llm_drift,
    score_accuracy,
    section_completeness,
)
from evaluate.utils import (
    NEWSLETTER_ROOT,
    load_fotmob_for_team,
    parse_date,
    resolve_newsletter_token,
)

WEIGHTS = {
    "score_accuracy":       0.30,
    "section_completeness": 0.20,
    "no_drift":             0.15,
    "no_hallucination":     0.25,
    "language_compliance":  0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "WEIGHTS must sum to 1.0"


# ─────────────────────────── per-newsletter evaluation ──────────────────────

def evaluate_newsletter(newsletter_file: Path) -> Optional[Dict]:
    """Run all metrics for one newsletter file. Returns None if no source data."""
    date_str = newsletter_file.parent.name
    nl_date = parse_date(date_str)
    if nl_date is None:
        return None

    token = resolve_newsletter_token(newsletter_file.stem)
    if token is None:
        return None

    fotmob_matches, source_players = load_fotmob_for_team(token, nl_date)
    if not fotmob_matches and not source_players:
        return None

    text = newsletter_file.read_text(encoding="utf-8")

    # Run each metric
    m1 = score_accuracy.evaluate(fotmob_matches, text)
    m3 = llm_drift.evaluate(text)                          # drift needed by m2
    m2 = section_completeness.evaluate(text, m3["detected"])
    m4 = hallucination.evaluate(text, source_players)
    m5 = language_compliance.evaluate(text)

    # Overall weighted score. A component is None when that metric genuinely
    # couldn't be measured (e.g. no source players to check hallucination
    # against) — treating an unmeasured metric as a perfect (or zero) score
    # would silently mask the gap, so instead we exclude it and renormalize
    # the weights over whatever *was* measured.
    components: Dict[str, Optional[float]] = {
        "score_accuracy":       m1["score"],
        "section_completeness": m2["score"],
        "no_drift":             0.0 if m3["detected"] else 1.0,
        "no_hallucination":     (1.0 - m4["rate"]) if m4["rate"] is not None else None,
        "language_compliance":  m5["ratio"],
    }
    assert set(components) == set(WEIGHTS), "components/WEIGHTS key mismatch"
    measured = {k: v for k, v in components.items() if v is not None}
    weight_sum = sum(WEIGHTS[k] for k in measured)
    overall = (
        sum(WEIGHTS[k] * v for k, v in measured.items()) / weight_sum
        if weight_sum > 0 else None
    )

    return {
        "date":    date_str,
        "team":    token.replace("_", " "),
        # raw metric results
        "score_accuracy":       m1,
        "section_completeness": m2,
        "llm_drift":            m3,
        "hallucination":        m4,
        "language_compliance":  m5,
        # scalars for aggregation
        "overall":              overall,
    }


# ─────────────────────────── report printing ────────────────────────────────

def _pct(v: Optional[float]) -> str:
    return "N/A" if v is None else f"{v * 100:.1f}%"


def print_report(results: List[Dict]) -> None:
    W = 72

    print("=" * W)
    print(f"{'FOOTBALL NEWS — AI EVALUATION REPORT':^{W}}")
    print("=" * W)

    weight_breakdown = (
        f"(score×{WEIGHTS['score_accuracy']:.0%}  "
        f"sections×{WEIGHTS['section_completeness']:.0%}  "
        f"drift×{WEIGHTS['no_drift']:.0%}  "
        f"halluc×{WEIGHTS['no_hallucination']:.0%}  "
        f"lang×{WEIGHTS['language_compliance']:.0%})"
    )

    for r in results:
        m1 = r["score_accuracy"]
        m2 = r["section_completeness"]
        m3 = r["llm_drift"]
        m4 = r["hallucination"]
        m5 = r["language_compliance"]

        print(f"\n[{r['date']}] {r['team']}")
        print(f"  {'─' * 48}")

        # 1. Score Accuracy
        print(f"  Score Accuracy       : {_pct(m1['score'])}")
        for match, ok in m1["details"]:
            tag = "✓" if ok else "✗"
            print(f"    {tag}  {match[0]} vs {match[1]}: {match[2]}-{match[3]}")

        # 2. Section Completeness
        hits_str = "  ".join(
            f"{'✓' if ok else '✗'} {name}"
            for name, ok in m2["hits"].items()
        )
        print(f"  Section Completeness : {_pct(m2['score'])}  [{hits_str}]")

        # 3. LLM Drift
        drift_str = (
            f"⚠  YES  (signals: {', '.join(m3['signals'][:2])}{'…' if len(m3['signals']) > 2 else ''})"
            if m3["detected"] else "✓  No"
        )
        print(f"  LLM Drift            : {drift_str}")

        # 4. Hallucination Rate
        h_extra = (
            f"  → {', '.join(sorted(m4['hallucinated_names']))}"
            if m4["hallucinated_names"] else ""
        )
        print(
            f"  Hallucination Rate   : {_pct(m4['rate'])}  "
            f"({m4['total_names']} names checked, lower is better){h_extra}"
        )

        # 5. Language Compliance
        lang_flag = "✓" if m5["passed"] else "✗"
        print(
            f"  Language Compliance  : {_pct(m5['ratio'])}  "
            f"{lang_flag} (target >{m5['target']*100:.0f}%)"
        )

        # Overall
        print(f"  {'─' * 48}")
        print(f"  Overall Score        : {_pct(r['overall'])}  {weight_breakdown}")

    # ── Aggregate ─────────────────────────────────────────────────────────────
    n = len(results)
    print("\n" + "=" * W)
    print(f"{'AGGREGATE  (n=' + str(n) + ')':^{W}}")
    print("=" * W)

    def avg_field(key: str, field: str) -> Optional[float]:
        vals = [r[key][field] for r in results if r[key].get(field) is not None]
        return sum(vals) / len(vals) if vals else None

    drift_n = sum(1 for r in results if r["llm_drift"]["detected"])
    overall_vals = [r["overall"] for r in results if r["overall"] is not None]
    overall_avg = sum(overall_vals) / len(overall_vals) if overall_vals else None

    print(f"  {'Score Accuracy':<24}: {_pct(avg_field('score_accuracy', 'score'))}")
    print(f"  {'Section Completeness':<24}: {_pct(avg_field('section_completeness', 'score'))}")
    print(f"  {'Hallucination Rate':<24}: {_pct(avg_field('hallucination', 'rate'))}  (lower is better)")
    print(f"  {'Language Compliance':<24}: {_pct(avg_field('language_compliance', 'ratio'))}")
    print(f"  {'LLM Drift Rate':<24}: {drift_n}/{n}  ({drift_n / n * 100:.0f}%)")
    print(f"  {'─' * 48}")
    print(f"  {'Overall Score':<24}: {_pct(overall_avg)}")


# ─────────────────────────── markdown report ────────────────────────────────

def render_report_markdown(results: List[Dict]) -> str:
    """Render the same report as print_report(), but as a markdown document
    suitable for saving to disk / uploading to GCS."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: List[str] = [
        "# Football News — AI Evaluation Report",
        "",
        f"_Generated: {generated_at}_",
        "",
    ]

    if not results:
        lines.append("No evaluatable newsletters found.")
        return "\n".join(lines) + "\n"

    weight_breakdown = (
        f"score×{WEIGHTS['score_accuracy']:.0%}, "
        f"sections×{WEIGHTS['section_completeness']:.0%}, "
        f"drift×{WEIGHTS['no_drift']:.0%}, "
        f"halluc×{WEIGHTS['no_hallucination']:.0%}, "
        f"lang×{WEIGHTS['language_compliance']:.0%}"
    )

    for r in results:
        m1 = r["score_accuracy"]
        m2 = r["section_completeness"]
        m3 = r["llm_drift"]
        m4 = r["hallucination"]
        m5 = r["language_compliance"]

        lines.append(f"## [{r['date']}] {r['team']}")
        lines.append("")
        lines.append("| Metric | Result |")
        lines.append("|---|---|")
        lines.append(f"| Score Accuracy | {_pct(m1['score'])} |")
        lines.append(f"| Section Completeness | {_pct(m2['score'])} |")
        drift_str = (
            f"⚠ YES (signals: {', '.join(m3['signals'][:2])}{'…' if len(m3['signals']) > 2 else ''})"
            if m3["detected"] else "✓ No"
        )
        lines.append(f"| LLM Drift | {drift_str} |")
        lines.append(
            f"| Hallucination Rate | {_pct(m4['rate'])} "
            f"({m4['total_names']} names checked, lower is better) |"
        )
        lang_flag = "✓" if m5["passed"] else "✗"
        lines.append(
            f"| Language Compliance | {_pct(m5['ratio'])} {lang_flag} "
            f"(target >{m5['target']*100:.0f}%) |"
        )
        lines.append(f"| **Overall Score** | **{_pct(r['overall'])}** ({weight_breakdown}) |")
        lines.append("")

        if m1["details"]:
            lines.append("Match results:")
            lines.append("")
            for match, ok in m1["details"]:
                tag = "✓" if ok else "✗"
                lines.append(f"- {tag} {match[0]} vs {match[1]}: {match[2]}-{match[3]}")
            lines.append("")

        hits_str = ", ".join(
            f"{'✓' if ok else '✗'} {name}" for name, ok in m2["hits"].items()
        )
        lines.append(f"Sections: {hits_str}")
        lines.append("")

        if m4["hallucinated_names"]:
            lines.append(f"Hallucinated names: {', '.join(sorted(m4['hallucinated_names']))}")
            lines.append("")

    # ── Aggregate ────────────────────────────────────────────────────────
    n = len(results)

    def avg_field(key: str, field: str) -> Optional[float]:
        vals = [r[key][field] for r in results if r[key].get(field) is not None]
        return sum(vals) / len(vals) if vals else None

    drift_n = sum(1 for r in results if r["llm_drift"]["detected"])
    overall_vals = [r["overall"] for r in results if r["overall"] is not None]
    overall_avg = sum(overall_vals) / len(overall_vals) if overall_vals else None

    lines.append(f"## Aggregate (n={n})")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Score Accuracy | {_pct(avg_field('score_accuracy', 'score'))} |")
    lines.append(f"| Section Completeness | {_pct(avg_field('section_completeness', 'score'))} |")
    lines.append(f"| Hallucination Rate | {_pct(avg_field('hallucination', 'rate'))} (lower is better) |")
    lines.append(f"| Language Compliance | {_pct(avg_field('language_compliance', 'ratio'))} |")
    lines.append(f"| LLM Drift Rate | {drift_n}/{n} ({drift_n / n * 100:.0f}%) |")
    lines.append(f"| **Overall Score** | **{_pct(overall_avg)}** |")

    return "\n".join(lines) + "\n"


# ─────────────────────────── json summary ───────────────────────────────────

def render_report_json(results: List[Dict]) -> Dict:
    """Compact machine-readable summary for downstream consumers (the dashboard).

    Distinct from render_report_markdown: this carries only the aggregate
    numbers a chart/scorecard needs, not per-newsletter detail.
    """
    if not results:
        return {"date": None, "n": 0, "overall_score": None, "metrics": {}}

    def avg_field(key: str, field: str) -> Optional[float]:
        vals = [r[key][field] for r in results if r[key].get(field) is not None]
        return sum(vals) / len(vals) if vals else None

    def pct(v: Optional[float]) -> Optional[float]:
        return round(v * 100, 1) if v is not None else None

    n = len(results)
    drift_n = sum(1 for r in results if r["llm_drift"]["detected"])
    overall_vals = [r["overall"] for r in results if r["overall"] is not None]
    overall_avg = sum(overall_vals) / len(overall_vals) if overall_vals else None
    hallucination_rate = avg_field("hallucination", "rate")

    dates = sorted(set(r["date"] for r in results))

    return {
        "date": dates[-1] if dates else None,
        "n": n,
        "overall_score": pct(overall_avg),
        "metrics": {
            "score_accuracy": pct(avg_field("score_accuracy", "score")),
            "section_completeness": pct(avg_field("section_completeness", "score")),
            "no_hallucination": pct(1 - hallucination_rate) if hallucination_rate is not None else None,
            "no_drift": pct(1 - (drift_n / n)) if n else None,
            "language_compliance": pct(avg_field("language_compliance", "ratio")),
        },
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
        help="Write the aggregate summary as JSON to this file path (for the dashboard)",
    )
    args = parser.parse_args()

    results: List[Dict] = []
    if NEWSLETTER_ROOT.exists():
        for date_dir in sorted(NEWSLETTER_ROOT.iterdir()):
            if not date_dir.is_dir():
                continue
            if args.date and date_dir.name != args.date:
                continue
            for nf in sorted(date_dir.glob("*.md")):
                r = evaluate_newsletter(nf)
                if r is None:
                    continue
                if args.team and args.team.lower() not in r["team"].lower():
                    continue
                results.append(r)

    if results:
        print_report(results)
    else:
        print("No evaluatable newsletters found.")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_report_markdown(results), encoding="utf-8")
        print(f"\nMarkdown report written to: {out_path}")

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(render_report_json(results), indent=2), encoding="utf-8")
        print(f"JSON summary written to: {json_path}")


if __name__ == "__main__":
    main()
