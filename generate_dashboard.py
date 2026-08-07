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
from google_sheet_parser import google_sheet_parser
from dashboard.render import render
from evaluate.evaluate_main import evaluate_newsletter, render_report_json
from evaluate.utils import NEWSLETTER_ROOT

BUCKET_NAME = "my-football-news"
GCS_DATA_PREFIX = "football-news/datas"
GCS_HISTORY_BLOB = "football-news/dashboard/eval-history.json"
REPO = "8804who/FootballNews"
WORKFLOW_SCHEDULES = {
    "collect_news": "daily 09:30 KST",
    "generate_newsletter": "Mon 10:00 KST",
    "send_mail": "Mon 11:00 KST",
}
SERVICE_ACCOUNT_FILE = "gen-lang-client.json"


def _gcs_client():
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    else:
        credentials, _ = google.auth.default(scopes=scopes)
    return storage.Client(credentials=credentials, project=credentials.project_id)


def _normalize(name: str) -> str:
    return re.sub(r"\s+", "", name).lower()


def fetch_subscribers():
    """Per-club subscriber counts, matched against setting.yml's team names by
    normalized (whitespace/case-insensitive) comparison so an inconsistent
    entry like "TottenhamHotspur" still counts toward "Tottenham Hotspur"
    rather than silently vanishing — while still flagging the inconsistency."""
    records = google_sheet_parser.get_all_records()
    raw_counts = {}
    for r in records:
        team = (r.get("어떤 팀의 소식을 받아보고 싶나요?") or "").strip()
        if team:
            raw_counts[team] = raw_counts.get(team, 0) + 1

    known_names = [t["name"] for t in TEAMS]
    known_by_norm = {_normalize(n): n for n in known_names}

    counts = {n: 0 for n in known_names}
    mismatches = set()
    for raw_team, count in raw_counts.items():
        norm = _normalize(raw_team)
        matched = known_by_norm.get(norm)
        if matched:
            counts[matched] += count
            if raw_team != matched:
                mismatches.add(raw_team)
        else:
            mismatches.add(raw_team)

    roster = [(name, counts[name]) for name in known_names]
    flag = None
    if mismatches:
        flag = (
            "the sheet stores " + ", ".join(f'"{m}"' for m in sorted(mismatches))
            + " which doesn't exactly string-match the team names used elsewhere in this codebase "
            "(counts above are still correct via normalized matching, but it's fragile — worth "
            "normalizing at the source)."
        )
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
    """Download the most recent newsletter week and its matching 7-day FotMob
    window into the real datas/ paths evaluate_main.py already reads from —
    mirrors how generate_newsletter.yaml's own CI step populates that
    directory, so no path assumptions change."""
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
    for i in range(1, 8):
        d = (base - timedelta(days=i)).strftime("%Y%m%d")
        for blob in bucket.list_blobs(prefix=f"{GCS_DATA_PREFIX}/fotmob/{d}/"):
            local = Path("datas/fotmob") / d / blob.name.split("/")[-1]
            local.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(local))

    return latest


def run_evaluation(date_str: str):
    date_dir = NEWSLETTER_ROOT / date_str
    if not date_dir.exists():
        return None
    results = []
    for nf in sorted(date_dir.glob("*.md")):
        r = evaluate_newsletter(nf)
        if r is not None:
            results.append(r)
    if not results:
        return None
    return render_report_json(results)


METRIC_LABELS = [
    ("score_accuracy", "Score Accuracy"),
    ("section_completeness", "Section Completeness"),
    ("no_hallucination", "No Hallucination"),
    ("no_drift", "No LLM Drift"),
    ("language_compliance", "Language Compliance"),
]


def shape_eval_current(summary: dict, date_str: str) -> dict:
    """Adapt evaluate_main.render_report_json's shape (overall_score, metrics
    dict keyed by internal names) to what render.py's presentation layer
    expects (overall, metrics as a display-ordered [(label, value)] list)."""
    iso_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    metrics = [
        (label, summary["metrics"][key])
        for key, label in METRIC_LABELS
        if summary["metrics"].get(key) is not None
    ]
    return {
        "date": iso_date,
        "n": summary["n"],
        "overall": summary["overall_score"],
        "metrics": metrics,
    }


def extract_editions(date_str: str):
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
        editions.append((team, score_line or "", headline))
    return editions, week_range


def load_eval_history(client):
    blob = client.bucket(BUCKET_NAME).blob(GCS_HISTORY_BLOB)
    if not blob.exists():
        return []
    return json.loads(blob.download_as_text())


def save_eval_history(client, history):
    blob = client.bucket(BUCKET_NAME).blob(GCS_HISTORY_BLOB)
    blob.upload_from_string(json.dumps(history, indent=2), content_type="application/json")


def append_if_new(history, date_str: str, overall_score: float, n: int):
    iso_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    if any(h["date"] == iso_date for h in history):
        return history, False
    history = history + [{"date": iso_date, "overall_score": overall_score, "n": n}]
    history.sort(key=lambda h: h["date"])
    return history, True


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
    history = load_eval_history(client)

    if latest_date:
        summary = run_evaluation(latest_date)
        editions, week_range = extract_editions(latest_date)
        if week_range:
            editions_week = f"week of {week_range}"
        if summary and summary["overall_score"] is not None:
            eval_current = shape_eval_current(summary, latest_date)
            history, appended = append_if_new(history, latest_date, summary["overall_score"], summary["n"])
            if appended:
                print(f"Appended {latest_date} to eval history ({summary['overall_score']}%).")
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
        "eval_history": history,
        "eval_caveat": eval_caveat,
        "editions": editions,
        "editions_week": editions_week,
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
