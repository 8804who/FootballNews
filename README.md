[한국어](README.ko.md) | English

# Football News

Collects football club news, generates a newsletter, and sends it to subscribers weekly.

## Workflow

1. **Collect** — Collect match reports and transfer news for configured Premier League clubs daily, from FotMob and Google News RSS. Each run looks 3 days back, so a day whose run failed is picked up by the next one.
2. **Generate** — Every Monday, once that morning's collection succeeds, generate a newsletter per club for the week before it (Monday 00:00 UTC → Monday 00:00 UTC). Matches and headlines are picked by kickoff/publish time, so each appears in exactly one edition.
3. **Evaluate** — Score each newsletter against its source data (scores, minute-by-minute match facts, each news item against the headline it links to, plus an LLM judge for meaning) and record tokens and cost. Then run yes/no checks on each edition (wrong, missing or repeated matches, another club's news, foreign links). They hold nothing: the results go to the dashboard.
4. **Send** — Send every club's newsletter to its subscribers, skipping unsubscribed addresses and anyone who already received this edition. Only a pipeline error (a failed step, a missing file, a failed send) stops or fails a send.
5. **Publish** — Generate and publish a dashboard for subscriber counts, workflow status, evaluation score history, and each edition's check results.

## Architecture

```
1) collect_news.py  (daily, 00:30 UTC)
     ├─ scrappers/fotmob.py    → renders FotMob match pages with Playwright + hits its API
     │                            → parses events/stats/substitutions/goals/cards, plus the full fixture list
     └─ scrappers/news_rss.py  → parses Google News RSS (keeps publish times, drops club landing pages)
     → writes team_daily_report_{team}_{matches,transfers}.md + _fixtures.json / team_daily_report_{team}.md
     → uploads to gs://my-football-news/football-news/datas/{fotmob,news_rss}/YYYYMMDD/
     → on Mondays, starts generate_newsletter

2) generate_newsletter.py  (Mondays, started by collect_news)
     downloads the collection folders from last Monday through today
     ├─ edition.py   → picks the week's matches / transfers / headlines by kickoff or publish
     │                 time, each once; drops previews of matches that have since been played
     └─ summarizers/llm.py (LLMSummarizer)
          → ChatOpenAI; prompt.yml rules as the system message, example.yml few-shot
            examples as earlier chat turns, the real input as the last message
          → the model cites headlines as [N1], [N2]…; summarizers/citations.py turns
            the tags into links to the collected stories
     └─ evaluate/evaluate_main.py → report.md + summary.json (metrics v2, judge on, cost from usage.json)
     └─ evaluate/gate.py          → yes/no checks → gate.json, shown on the dashboard (report-only)
     → uploads newsletter/ and evaluation/ to GCS, then starts send_mail

3) send_mail.py  (started by generate_newsletter)
     downloads this week's newsletter/ (with sent.json) from GCS
     ├─ google_sheet_parser.py      → per-team subscriber emails from the "신청자 목록"
     │                                 (signup list) worksheet, minus the "수신거부" worksheet
     └─ email_sender/smtp_sender.py → sends via Gmail SMTP with an unsubscribe footer
     → records who got this edition in sent.json, so a re-run never emails anyone twice

4) generate_dashboard.py  (after collect_news / generate_newsletter / send_mail finish)
     aggregates subscriber counts, workflow run history, evaluation score history, and each edition's checks
     └─ dashboard/render.py → generates dashboard → deployed to GitHub Pages
```

## Code structure

```
config.py               Config
edition.py              Which matches and headlines belong to a weekly edition
team_names.py           Resolves club spellings ("Man Utd", "Spurs", "토트넘") via teams.yml
notify.py               Emails the operator when a workflow fails

scrappers/
  fotmob.py              Extracts events/stats/substitutions/goals/cards from
                          FotMob match pages via Playwright.
  news_rss.py             Google RSS news collection
  fbref.py, fpl.py         Unused

summarizers/
  llm.py                  Newsletter generation
  citations.py            Turns the model's [N1] source tags into links

evaluate/                 Scores generated newsletters against fotmob / RSS source data (metrics v2)
    score_accuracy.py        20% — is every scoreboard row right, with no repeated or invented match?
    match_facts.py           15% — do "minute + player" claims match the match events?
    news_grounding.py         15% — does each news item match the headline it links to?
    hallucination.py          15% — are there names in no source?
    section_completeness.py  10% — are the sections this week's source calls for present?
    language_compliance.py    10% — is the text Korean, apart from the English names
                                     the style guide requires? (target 95%)
    llm_drift.py               5% — did the model drift into chatbot mode?
    judge.py                  10% — LLM judge: does each item say what its source says? (--judge)
  gate.py                  Yes/no checks per edition, shown on the dashboard (report-only)
  cost.py, pricing.yml     Token usage → USD (prices per model, kept up to date by hand)
  harness.py, runs.yml     Compare prompt / model variants on past editions
  backfill.py              Re-score past weeks after a metric change
  golden.py                Freeze a real edition as a regression case (tests/golden/)
  utils.py                 Shared parsing / source-loading logic

email_sender/
  email_sender.py          EmailSender abstract class
  smtp_sender.py            Gmail SMTP + markdown-it-py to convert Markdown to
                          HTML before sending

dashboard/
  render.py                Renders collected stats (subscribers, workflow
                          status, evaluation history) into the dashboard

tests/                    Unit tests (python -m unittest discover -s tests)
```

### Configuration layers

`config.py` reads the following files, in order, at import time, and exposes them as constants.

| File | Purpose |
|---|---|
| `api.yml` | API keys/credentials (GitHub Secrets used in GitHub Actions); optional `ALERT_EMAIL` |
| `setting.yml` | Target teams, the LLM model, and the footer links (`newsletter.signup_url`, `newsletter.unsubscribe_url`) |
| `prompt.yml` | LLM system prompt and per-task prompts |
| `example.yml` | Few-shot examples for newsletter writing — fictional names only |
| `teams.yml` | FotMob team info (ID, name) mapping, and other spellings of each club (`aliases`) |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Usage

```bash
# Collect data per team
python collect_news.py
python collect_news.py --team Arsenal

# Generate newsletter (the edition for this week's Monday)
python generate_newsletter.py
python generate_newsletter.py --date 20261026 --team Chelsea   # regenerate one club's edition

# Evaluate
python evaluate/evaluate_main.py
python evaluate/evaluate_main.py --date 20260306
python evaluate/evaluate_main.py --team Liverpool
python evaluate/evaluate_main.py --date 20261102 --judge \
  --json-output datas/evaluation/20261102/summary.json      # what CI runs

# Compare prompt / model variants on past editions (evaluate/runs.yml)
python evaluate/harness.py --judge                           # → evaluate/runs/report.md
python evaluate/harness.py --rescore --judge                 # after a metric change, no regeneration

# Re-score past weeks after changing a metric (local; --upload to update the dashboard)
python evaluate/backfill.py

# Turn a newly found defect into a regression case
python evaluate/golden.py --name <case> --date <YYYYMMDD> --team <Team> --why "<what's wrong>"

# Edition checks, report-only (writes datas/newsletter/{date}/gate.json for the dashboard)
python evaluate/gate.py --date 20261026

# Send newsletter
python send_mail.py --dry-run               # print what would be sent
python send_mail.py

# Generate dashboard
python generate_dashboard.py

# Tests
python -m unittest discover -s tests
```

## Automation

| Workflow | Runs | Does |
|---|---|---|
| `collect_news.yaml` | Daily 00:30 UTC (09:30 KST) | Collect + upload to GCS; on Mondays, start `generate_newsletter` |
| `generate_newsletter.yaml` | Started by Monday's `collect_news` (or by hand) | Generate → evaluate → edition checks (report-only) → upload → start `send_mail` |
| `send_mail.yaml` | Started by `generate_newsletter` (or by hand) | Send every club's edition, skipping anyone already sent it |
| `dashboard.yaml` | After any of the workflows above finish | Rebuild + deploy the status dashboard (each week's stored summary.json and gate.json) |
| `tests.yaml` | Every push and pull request | Unit tests + the golden regression cases (no secrets needed) |

The three are chained instead of scheduled separately so a newsletter is never generated before the weekend's matches are collected. GitHub starts scheduled runs hours late (about 5 hours in Oct 2026), so the whole chain starts late too.

Required GitHub Secrets: `OPENAI_API_KEY`, `GCP_SA_KEY`, `GOOGLE_CLOUD_EMAIL`, `GOOGLE_CLOUD_SPREADSHEET_URL`, `SMTP_USERNAME`, `SMTP_PASSWORD`. Optional: `ALERT_EMAIL` (where alerts go; defaults to `SMTP_USERNAME`).

## When something goes wrong

Every workflow emails the operator when it fails. Content problems don't stop a send.

- **A club is flagged on the dashboard** — its edition card lists why: a wrong, missing or repeated match, a finished match that was never collected, few-shot example text, another club's news, or a link to a headline this club didn't have. The edition was already sent; fix the cause before next week (regenerating with `--date`/`--team` and checking locally helps).
- **Monday's collection failed** — no newsletter is generated until a collection succeeds. Re-run `collect_news` (on a Monday it starts the newsletter again), or run `generate_newsletter` with `send_after` ticked.
- **Some emails failed** — re-run `send_mail`. `sent.json` makes it skip everyone who already received the edition.
- **Unsubscribes** — every email has a 수신거부 link and a `List-Unsubscribe` header. By default they open an email to the sender address; set `newsletter.unsubscribe_url` in `setting.yml` to use a Google Form (`{email}` is filled in). Addresses in a "수신거부" worksheet of the subscriber spreadsheet are never emailed.
- **Privacy** — this repository is public, and so are its workflow logs; `send_mail.py` only ever logs masked addresses (`j***@gmail.com`).
