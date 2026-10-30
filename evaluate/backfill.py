#!/usr/bin/env python3
"""
backfill.py — re-score past weeks with the current metrics.

Scores are only comparable within one metrics version (METRICS_VERSION in
evaluate_main.py), and the dashboard's trend line only shows the current
one. After changing a metric, re-score the weeks you have locally so the
trend continues instead of restarting:

    python download_from_gcs.py --days 90 --types fotmob,news_rss,newsletter
    python evaluate/backfill.py              # writes datas/evaluation/<date>/summary.json
    python evaluate/backfill.py --upload     # also puts them in GCS and the dashboard history

Only Monday editions are scored (other dates are manual or test runs), and a
week is skipped when most of its source folders aren't on disk — scoring it
would blame the newsletter for data that just wasn't downloaded. --judge adds
the LLM check (about $0.05 a week).
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running from the project root: python evaluate/backfill.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import edition
from evaluate.evaluate_main import METRICS_VERSION, evaluate_newsletter, render_report_json
from evaluate.utils import DATA_ROOT, NEWSLETTER_ROOT, parse_date


def missing_folders(date_str: str) -> list:
    date = parse_date(date_str)
    start, _ = edition.edition_window(date)
    return [d for d in edition.folder_dates(start, date) if not (DATA_ROOT / "fotmob" / d).exists()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-score past weeks with the current metrics.")
    parser.add_argument("--upload", action="store_true",
                        help="Also upload the summaries to GCS and update the dashboard's history")
    parser.add_argument("--judge", action="store_true", help="Also run the LLM faithfulness judge")
    args = parser.parse_args()

    weeks = sorted(
        d for d in NEWSLETTER_ROOT.iterdir()
        if d.is_dir() and parse_date(d.name) and parse_date(d.name).weekday() == 0
        and any(d.glob("newsletter_*.md"))
    )
    summaries = {}
    for week in weeks:
        missing = missing_folders(week.name)
        if len(missing) > 2:
            print(f"{week.name}: skipped — {len(missing)} source folders not on disk (download more days)")
            continue
        results = [r for r in (evaluate_newsletter(f, use_judge=args.judge)
                               for f in sorted(week.glob("newsletter_*.md"))) if r]
        if not results:
            continue
        summary = render_report_json(results, judged=args.judge)
        out = DATA_ROOT / "evaluation" / week.name / "summary.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summaries[week.name] = summary
        print(f"{week.name}: {summary['overall_score']}% overall (n={summary['n']}) → {out}")

    print(f"\n{len(summaries)} week(s) scored with metrics v{METRICS_VERSION}.")
    if not args.upload or not summaries:
        return

    from generate_dashboard import (BUCKET_NAME, GCS_DATA_PREFIX, _gcs_client, append_if_new,
                                    load_eval_history, save_eval_history)
    client = _gcs_client()
    bucket = client.bucket(BUCKET_NAME)
    history = load_eval_history(client)
    for date_str, summary in summaries.items():
        bucket.blob(f"{GCS_DATA_PREFIX}/evaluation/{date_str}/summary.json").upload_from_string(
            json.dumps(summary, indent=2), content_type="application/json")
        history, _ = append_if_new(history, date_str, summary)
    save_eval_history(client, history)
    print(f"Uploaded {len(summaries)} summaries and updated the dashboard history.")


if __name__ == "__main__":
    main()
