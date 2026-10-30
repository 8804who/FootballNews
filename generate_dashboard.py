import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from google.cloud import storage
from google.oauth2 import service_account
import google.auth

from config import TEAMS
from google_sheet_parser import EMAIL_COLUMN, TEAM_COLUMN, google_sheet_parser
from dashboard.render import render
from evaluate import gate
from evaluate.evaluate_main import LABELS, METRICS_VERSION, WEIGHTS, evaluate_newsletter, render_report_json
from evaluate.utils import NEWSLETTER_ROOT, resolve_newsletter_token
from team_names import canonical

BUCKET_NAME = "my-football-news"
GCS_DATA_PREFIX = "football-news/datas"
GCS_HISTORY_BLOB = "football-news/dashboard/eval-history.json"
REPO = "8804who/FootballNews"
WORKFLOW_SCHEDULES = {
    "collect_news": "daily 09:30 KST",
    "generate_newsletter": "Mon, after collect_news",
    "send_mail": "Mon, after generate_newsletter",
}
SERVICE_ACCOUNT_FILE = "gen-lang-client.json"


def _gcs_client():
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    else:
        credentials, _ = google.auth.default(scopes=scopes)
    return storage.Client(credentials=credentials, project=credentials.project_id)


def fetch_subscribers():
    """Per-club counts of active subscribers (one per address, unsubscribed
    addresses left out). Team answers are matched through teams.yml's aliases,
    the same way send_mail.py matches them, so "TottenhamHotspur" still counts
    toward "Tottenham Hotspur" — while still flagging answers that differ
    from the team name, and loudly flagging ones that match no club at all."""
    records = google_sheet_parser.get_all_records()
    unsubscribed = google_sheet_parser.get_unsubscribed()
    signups = set()
    for r in records:
        team = str(r.get(TEAM_COLUMN) or "").strip()
        email = str(r.get(EMAIL_COLUMN) or "").strip().lower()
        if team and email and email not in unsubscribed:
            signups.add((team, email))

    known_names = [t["name"] for t in TEAMS]
    counts = {n: 0 for n in known_names}
    variants, unmatched = set(), set()
    for raw_team, _ in signups:
        matched = canonical(raw_team)
        if matched in counts:
            counts[matched] += 1
            if raw_team != matched:
                variants.add(raw_team)
        else:
            unmatched.add(raw_team)

    roster = [(name, counts[name]) for name in known_names]
    notes = []
    if unmatched:
        notes.append(
            "sign-ups for " + ", ".join(f'"{m}"' for m in sorted(unmatched))
            + " match no configured club, so those subscribers receive nothing — fix the answer "
            "in the sheet or add an alias to teams.yml"
        )
    if variants:
        notes.append(
            "the sheet stores " + ", ".join(f'"{m}"' for m in sorted(variants))
            + " rather than the exact team name (counted through teams.yml's aliases; a fixed "
            "dropdown in the sign-up form would stop new variants)"
        )
    flag = "; ".join(notes) + "." if notes else None
    return roster, flag


def fetch_workflow_runs():
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.get(
        f"https://api.github.com/repos/{REPO}/actions/runs",
        params={"per_page": 100},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    runs = resp.json()["workflow_runs"]

    by_name = {}
    for r in runs:
        by_name.setdefault(r["name"], []).append(r)

    workflows = []
    for name, schedule in WORKFLOW_SCHEDULES.items():
        items = sorted(by_name.get(name, []), key=lambda r: r["created_at"], reverse=True)
        if not items:
            continue
        total = len(items)
        ok = sum(1 for r in items if r["conclusion"] == "success")
        history = []
        for r in reversed(items[:30]):
            when = r["created_at"][:16].replace("T", " ") + " UTC"
            status = "good" if r["conclusion"] == "success" else (
                "warn" if r["conclusion"] in ("cancelled", "skipped", "neutral", None) else "crit"
            )
            history.append((when, status))
        workflows.append({
            "name": name,
            "ok": ok,
            "total": total,
            "last_run": items[0]["created_at"][:16].replace("T", " ") + " UTC",
            "schedule": schedule,
            "history": history,
        })
    return workflows


def download_latest_week(client) -> str | None:
    """Download the most recent newsletter week and the FotMob + RSS folders
    its edition was built from into the real datas/ paths evaluate_main.py
    reads — the same 9 folders generate_newsletter.yaml downloads. (RSS is
    needed too: without it, every name that came from a headline is scored
    as hallucinated.)"""
    bucket = client.bucket(BUCKET_NAME)
    it = client.list_blobs(bucket, prefix=f"{GCS_DATA_PREFIX}/newsletter/", delimiter="/")
    list(it)
    dates = sorted(p.split("/")[-2] for p in it.prefixes)
    if not dates:
        return None
    latest = dates[-1]

    for blob in bucket.list_blobs(prefix=f"{GCS_DATA_PREFIX}/newsletter/{latest}/"):
        local = Path("datas/newsletter") / latest / blob.name.split("/")[-1]
        local.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(local))

    base = datetime.strptime(latest, "%Y%m%d")
    for i in range(0, 9):
        d = (base - timedelta(days=i)).strftime("%Y%m%d")
        for data_type in ("fotmob", "news_rss"):
            for blob in bucket.list_blobs(prefix=f"{GCS_DATA_PREFIX}/{data_type}/{d}/"):
                local = Path("datas") / data_type / d / blob.name.split("/")[-1]
                local.parent.mkdir(parents=True, exist_ok=True)
                blob.download_to_filename(str(local))

    return latest


def run_evaluation(date_str: str):
    """Score a week now — only for weeks without a stored summary.json (before
    Oct 30 2026); CI stores one for every new week."""
    date_dir = NEWSLETTER_ROOT / date_str
    if not date_dir.exists():
        return None
    results = []
    for nf in sorted(date_dir.glob("newsletter_*.md")):
        r = evaluate_newsletter(nf)
        if r is not None:
            results.append(r)
    if not results:
        return None
    return render_report_json(results)


def load_summary(client, date_str: str):
    """The week's summary.json written by CI, if it uses the current metrics."""
    blob = client.bucket(BUCKET_NAME).blob(f"{GCS_DATA_PREFIX}/evaluation/{date_str}/summary.json")
    if not blob.exists():
        return None
    summary = json.loads(blob.download_as_text())
    return summary if summary.get("metrics_version") == METRICS_VERSION else None


def shape_eval_current(summary: dict, date_str: str) -> dict:
    """Adapt evaluate_main.render_report_json's shape (overall_score, metrics
    dict keyed by internal names) to what render.py's presentation layer
    expects (overall, metrics as a display-ordered [(label, value)] list)."""
    iso_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    metrics = [
        (LABELS[key], summary["metrics"][key])
        for key in WEIGHTS
        if summary["metrics"].get(key) is not None
    ]
    return {
        "date": iso_date,
        "n": summary["n"],
        "overall": summary["overall_score"],
        "metrics": metrics,
        # Built from WEIGHTS so the legend can't drift from the real weighting.
        "weights": " · ".join(f"{LABELS[k].split(' (')[0].lower()} {w:.0%}" for k, w in WEIGHTS.items()),
    }


def load_checks(date_str: str) -> dict:
    """evaluate/gate.py's findings per club ({team: {problems, warnings}}).
    CI writes gate.json next to the newsletters; a week without one (before
    Oct 30 2026) is checked now. Report-only: no edition was held for these."""
    path = NEWSLETTER_ROOT / date_str / "gate.json"
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8")).get("teams", {})
        return gate.run_gate(date_str)["teams"]
    except Exception as e:
        print(f"⚠ Could not load the edition checks for {date_str}: {e}")
        return {}


def checks_note(checks: dict) -> str:
    if not checks:
        return ""
    flagged = sum(1 for c in checks.values() if c.get("problems"))
    return f"{flagged} of {len(checks)} flagged by the checks" if flagged else "all checks passed"


def extract_editions(date_str: str, checks: dict = None):
    date_dir = NEWSLETTER_ROOT / date_str
    if not date_dir.exists():
        return [], None
    editions = []
    week_range = None
    for nf in sorted(date_dir.glob("*.md")):
        text = nf.read_text(encoding="utf-8")
        m = re.match(r"^#\s*(.+?)\s*[·\-]\s*주간.*?\(([^)]+)\)", text)
        team = m.group(1).strip() if m else nf.stem.replace("newsletter_", "").replace("_", " ")
        if m and week_range is None:
            week_range = m.group(2).strip()

        hm = re.search(r"헤드라인.*?\n\s*\*\*(.+?)\*\*", text)
        headline = hm.group(1).strip() if hm else "(no headline found)"

        score_line = None
        table_rows = [line for line in text.splitlines() if line.strip().startswith("|")]
        if len(table_rows) >= 3:
            cells = [c.strip() for c in table_rows[2].split("|")[1:-1]]
            if len(cells) >= 2:
                score_line = f"{cells[0]}  {cells[1]}"
        check = (checks or {}).get((resolve_newsletter_token(nf.stem) or "").replace("_", " "))
        editions.append((team, score_line or "", headline, check))
    return editions, week_range


def load_eval_history(client):
    blob = client.bucket(BUCKET_NAME).blob(GCS_HISTORY_BLOB)
    if not blob.exists():
        return []
    return json.loads(blob.download_as_text())


def save_eval_history(client, history):
    blob = client.bucket(BUCKET_NAME).blob(GCS_HISTORY_BLOB)
    blob.upload_from_string(json.dumps(history, indent=2), content_type="application/json")


def history_entry(date_str: str, summary: dict) -> dict:
    return {
        "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
        "overall_score": summary["overall_score"],
        "n": summary["n"],
        "metrics_version": summary.get("metrics_version", METRICS_VERSION),
        "metrics": summary.get("metrics", {}),
    }


def append_if_new(history, date_str: str, summary: dict):
    """Add the week, or replace an entry scored by an older metrics version.
    Entries without a version are from before versioning (v1)."""
    entry = history_entry(date_str, summary)
    same_week = [h for h in history if h["date"] == entry["date"]]
    if any(h.get("metrics_version", 1) == entry["metrics_version"] for h in same_week):
        return history, False
    history = [h for h in history if h["date"] != entry["date"]] + [entry]
    history.sort(key=lambda h: h["date"])
    return history, True


def current_trend(history):
    """Only weeks scored by the current metrics are comparable on one line."""
    return [h for h in history if h.get("metrics_version", 1) == METRICS_VERSION]


def main():
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print("Fetching subscribers...")
    roster, roster_flag = fetch_subscribers()

    print("Fetching workflow run history...")
    workflows = fetch_workflow_runs()

    client = _gcs_client()

    print("Downloading latest newsletter week + source data...")
    latest_date = download_latest_week(client)

    eval_current = None
    eval_caveat = None
    editions = []
    editions_week = "no data yet"
    checks = {}
    history = load_eval_history(client)

    if latest_date:
        summary = load_summary(client, latest_date) or run_evaluation(latest_date)
        checks = load_checks(latest_date)
        editions, week_range = extract_editions(latest_date, checks)
        if week_range:
            editions_week = f"week of {week_range}"
        if summary and summary["overall_score"] is not None:
            eval_current = shape_eval_current(summary, latest_date)
            history, appended = append_if_new(history, latest_date, summary)
            if appended:
                print(f"Added {latest_date} to eval history ({summary['overall_score']}%, metrics v{METRICS_VERSION}).")
                save_eval_history(client, history)
        else:
            eval_caveat = (
                f"the most recent newsletter week ({latest_date}) couldn't be scored — "
                "its matching FotMob source data wasn't available in GCS for the lookback window."
            )
    else:
        eval_caveat = "no newsletter data found in GCS yet."

    data = {
        "generated_at": generated_at,
        "roster": roster,
        "roster_flag": roster_flag,
        "workflows": workflows,
        "eval_current": eval_current,
        "eval_history": current_trend(history),
        "eval_caveat": eval_caveat,
        "editions": editions,
        "editions_week": editions_week,
        "checks_note": checks_note(checks),
    }

    out_dir = Path("dist")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(render(data), encoding="utf-8")

    assets_src = Path("dashboard/assets")
    assets_dst = out_dir / "assets"
    if assets_src.exists():
        import shutil
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)

    print(f"Dashboard written to {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
