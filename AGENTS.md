# AGENTS.md

This file provides guidance to Codex (claude.ai/code) when working with code in this repository.

## Project Overview

Football News is a Python-based automated newsletter pipeline that:
1. Scrapes match/transfer data for Premier League, LaLiga, Bundesliga and Ligue 1 clubs (FotMob, Google News RSS) daily
2. Generates Korean-language newsletters via OpenAI (LangChain) weekly, then scores them with a source-grounded evaluation harness
3. Distributes them via Gmail SMTP to subscribers listed in a Google Sheet, weekly
4. Runs fully automated via three chained GitHub Actions workflows (collect → generate → send), using Google Cloud Storage as the handoff store between them

## Commands

```bash
# Activate venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (required for fotmob scraper)
playwright install chromium

# Collect data for all configured teams (run daily; each run looks 3 days back)
python collect_news.py
python collect_news.py --team Arsenal      # one team

# Pull collected data down from GCS for local runs (CI does this with raw `gcloud storage cp` instead)
python download_from_gcs.py                # last 8 days + today, all data types
python download_from_gcs.py --date 20260803 --types fotmob,news_rss

# Generate the edition for this week's Monday (run weekly)
python generate_newsletter.py
python generate_newsletter.py --date 20261026 --team Chelsea   # regenerate one club's edition

# Evaluate newsletter accuracy against source data
python evaluate/evaluate_main.py
python evaluate/evaluate_main.py --date 20260306   # only this date
python evaluate/evaluate_main.py --team Liverpool  # only this team
python evaluate/evaluate_main.py --output datas/evaluation/20260306/report.md
python evaluate/evaluate_main.py --date 20261102 --judge --json-output datas/evaluation/20261102/summary.json  # what CI runs

# Compare prompt / model variants on past editions (costs API money; outputs in evaluate/runs/, gitignored)
python evaluate/harness.py --judge
python evaluate/harness.py --rescore --judge     # after a metric change: re-score, don't regenerate
python evaluate/pairwise.py before after         # blind A/B of two harness runs (LLM, both orders) + blind files for your own read

# After changing a metric: bump METRICS_VERSION, then re-score past weeks (local unless --upload)
python evaluate/backfill.py

# Freeze a newly found defect as a regression case, then hand-write its "expect" block
python evaluate/golden.py --name <case> --date <YYYYMMDD> --team <Team> --why "<what's wrong>"

# Yes/no checks per edition → datas/newsletter/{date}/gate.json, shown on the dashboard (report-only)
python evaluate/gate.py --date 20261026

# Send the current week's generated newsletters to subscribers (run weekly, after generate)
python send_mail.py --dry-run               # never emails anyone; use this to test the send path
python send_mail.py --test Arsenal          # this edition's Arsenal newsletter to ALERT_EMAIL only (sheet and sent.json untouched)
python send_mail.py

# Tests (unittest, no pytest) — no network, no email
python -m unittest discover -s tests
```

Never run `send_mail.py` without `--dry-run` or `--test` locally: it emails real subscribers.

## Configuration

The project uses layered config loaded in `config.py`:
- **`api.yml`** — local API keys and credentials (gitignored; takes precedence over env vars)
- **Environment variables** — used in CI/CD via GitHub Secrets when `api.yml` is absent
- **`setting.yml`** — target teams, OpenAI model, and email footer links (`newsletter.signup_url`, `newsletter.unsubscribe_url`)
- **`prompt.yml`** — LLM system prompt and per-section prompt templates
- **`example.yml`** — few-shot examples fed to the LLM. Every name in it must stay fictional: `evaluate/gate.py` flags any edition containing one
- **`teams.yml`** — team ID mappings across different data sources (api_football, fbref, FPL, fotmob), plus `aliases` (other spellings of each club, used everywhere club names are compared via `team_names.py`)
- **`ALERT_EMAIL`** (api.yml key or env var, optional) — where `notify.py` sends workflow-failure alerts; defaults to the SMTP sender

## Architecture

### Data Flow

The pipeline is three scripts in three workflows chained by `gh workflow run` (collect → on Mondays generate → send), handed off via GCS (bucket `my-football-news`, prefix `football-news/datas`):

```
1. collect_news.py  (daily 00:30 UTC / 09:30 KST, GitHub cron; looks LOOKBACK_DAYS=3 back so a failed day self-heals)
     ├── scrappers/fotmob.py      → FotMob (Playwright + API) → datas/fotmob/YYYYMMDD/team_daily_report_{team}_{matches,transfers}.md
     │                                                          + team_daily_report_{team}_fixtures.json (full fixture list, shootouts)
     │                                                          + team_daily_report_{team}_overview.json (league table, injuries)
     └── scrappers/news_rss.py    → Google News RSS           → datas/news_rss/YYYYMMDD/team_daily_report_{team}.md
                                     ("- [YYYY-MM-DD HH:MM] headline (url)"; club landing pages dropped)
                                  → BBC Sport club feed       → team_daily_report_{team}_bbc.json (≤6 stories with summaries)
     → gcloud storage cp → gs://my-football-news/football-news/datas/{fotmob,news_rss}/YYYYMMDD/
     → Mondays (UTC): gh workflow run generate_newsletter.yaml -f send_after=true

2. generate_newsletter.py  (weekly, started by collect_news)
     download the folders from last Monday through today (9 folders)
     ├── edition.py               → the edition covers last Monday 00:00 UTC → this Monday 00:00 UTC;
     │                               matches/transfers/headlines selected by kickoff/publish time, each once
     ├── summarizers/llm.py (LLMSummarizer) → ChatOpenAI, few-shot examples as chat turns
     │                               then summarizers/tidy.py (dashes, title line breaks, club particles)
     ├── summarizers/blocks.py   → 📍 순위 & 다음 경기 · 🏥 결장 예상, rendered by code from FotMob (no LLM)
     └── → datas/newsletter/YYYYMMDD/newsletter_{team}.md + inputs/{team}.json (what it was generated from)
     └── evaluate/evaluate_main.py → datas/evaluation/YYYYMMDD/report.md (weighted metrics, non-blocking)
     └── evaluate/gate.py          → datas/newsletter/YYYYMMDD/gate.json (report-only, shown on the dashboard)
     → upload newsletter/ and evaluation/ to GCS → gh workflow run send_mail.yaml

3. send_mail.py  (weekly, started by generate_newsletter)
     download this week's newsletter/ (with sent.json) from GCS
     ├── google_sheet_parser.py   → Google Sheet "신청자 목록" worksheet → per-team subscriber emails
     │                               (minus the optional "수신거부" worksheet)
     └── email_sender/smtp_sender.py → Gmail SMTP → subscribers (footer + List-Unsubscribe)
     → sent.json (sha256 per recipient) uploaded back, so re-runs never double-send
```

A collection folder's date is the day `collect_news.py` *ran*, not the match date, and each run repeats the last few days. Never select edition data by folder date — go through `edition.py` (generate, evaluate, the gate and the email subject all do).

`scrappers/fbref.py` and `scrappers/fpl.py` exist (Football Reference HTML, FPL public API) but are **not** wired into `collect_news.py` — they're standalone scripts with their own `if __name__ == "__main__"` blocks, runnable on their own but not part of the automated pipeline. `teams.yml`/`config.py` still load FBref/FPL team mappings for them.

### Key Details

- **fotmob.py** is the most complex scraper: uses Playwright to render match pages and extract events, stats, substitutions, goals, cards, etc.
- **Adding a club**: `setting.yml` + its FotMob id, BBC slug, `aliases` and opponent `readings` in `teams.yml`. Home/away comes from FotMob's team id and the table from the club's `primaryLeagueId`, because FotMob's fixtures use short names ("PSG"). Never give PSG a bare "Paris" alias: `normalize()` drops "FC", so it would also match Paris FC.
- **llm.py** sends the rules as a system message, each `example.yml` few-shot example as a labelled earlier user/assistant turn, and the real input as the last message, so the model answers the real input and never an example (sent as one string, it answered examples and invented transfer news). Tone is defined in `prompt.yml`.
- **prompt.yml** entries are text blocks (`|`), each sent to the model as one block; `tests/test_tidy.py` guards that. Keep prompt.yml and example.yml free of long dashes and arrows (the model copies them) and of real names.
- **News sources** go to the model as tagged lines (`- [N1] date · outlet · 보도|가십 · headline`, plus `  요약: …` for BBC stories); the model ends each item with tags, and `summarizers/citations.py` replaces them with links. The model never handles URLs, and never invents likelihood percentages. News sub-sections are `✅ 확정 소식` (done and reported as fact, never gossip), `🧪 루머`, `🎭 드라마 앵글` (`newsletter_sections.py`).
- **Edition news** (`edition.edition_news`, generation only): BBC wins duplicates, Google's BBC items are dropped on BBC days, and reports of matches already on the scoreboard are dropped. The evaluation scores new editions against `inputs/{team}.json`, and editions without one against `edition.load_news` as before, so old scores don't move.
- **Code-rendered blocks** (`summarizers/blocks.py`) use only an overview snapshot collected after the edition week (`edition.load_overview`), and the table only when its games played match FotMob's finished league fixtures; otherwise the block is left out. The metrics and the gate skip them (`newsletter_sections.strip_data_blocks`).
- **Style** (`evaluate/style.py`, report-only, in the harness report): prompt-banned habits, a held-out set the prompt never names, headline length. Judge voice changes with `evaluate/pairwise.py` too, and read its blind files yourself; the LLM judge favours its own wordier style.
- **Newsletter output is always in Korean** — proper nouns (team names, player names) stay in English.
- **email_sender/email_sender.py** defines an `EmailSender` ABC; `smtp_sender.py` is currently the only implementation (Gmail SMTP + Markdown→styled-HTML via `markdown-it-py`, plain-text alternative, optional footer/headers). Swap in another provider by implementing the same interface.
- **evaluate/** scores each generated newsletter against its source data on 8 weighted metrics, version 2 (see `evaluate/evaluate_main.py`'s `WEIGHTS` and `METRICS_VERSION`): score accuracy (20%, `score_accuracy.py` — every scoreboard row, club aliases understood, repeated/invented rows count against it), match facts (15%, `match_facts.py` — "minute + player" claims vs. match events, paired by Korean clause structure), news grounding (15%, `news_grounding.py` — each item vs. the headline it links to), no hallucinated names (15%, `hallucination.py`), section completeness (10%, `section_completeness.py` — the sections the week's source calls for), Korean-language compliance (10%, `language_compliance.py`, English proper nouns excluded, target 95%), no LLM drift (5%, `llm_drift.py`), and faithfulness (10%, `judge.py` — LLM judge, `--judge` only, gpt-5-mini with a 3-vote majority). A metric that can't be measured is excluded and the remaining weights renormalized. Coverage (collected ÷ FotMob-finished matches) is reported beside the score, not in it. Every edition is scored, including news-only weeks. Name regexes use Latin lookarounds instead of `\b`, because Hangul particles ("Bruyne는") are word characters.
- **Changing a metric** changes what old scores mean: bump `METRICS_VERSION`, re-run `evaluate/backfill.py`, and make sure `tests/golden/` still passes (real defects that must keep being caught; `test_golden.py` replays them). The dashboard reads each week's stored `summary.json` and only draws a trend within one version.
- **Cost**: every LLM call is recorded (`summarizers.llm.usage_record`) into `usage.json` next to the newsletters; `evaluate/cost.py` prices it with `evaluate/pricing.yml` (update by hand when prices change). Newer models (gpt-5.4+) don't reason unless `reasoning_effort` is set — the harness compares both.
- **evaluate/gate.py** runs yes/no checks (scoreboard vs source matches, uncollected finished fixtures, few-shot names, names only in another club's sources, links not among the club's headlines). **Report-only, by the owner's decision (2026-10-30): nothing blocks a send.** A failing club is written as `flagged` in `gate.json` and shown on its dashboard edition card (`generate_dashboard.load_checks`); `send_mail.py` never reads it. Only pipeline errors (a failed step, a missing file, a failed send) stop or fail a send. Don't reintroduce holds or hold alerts without asking. Replayed on 72 past editions it flagged only real defects — keep it that way; a check that cries wolf gets ignored.
- **Privacy**: the repo and its Actions logs are public. Never print subscriber addresses — `send_mail.mask()` them.
- **Google Cloud Storage** is the persistent store handing data between all three GitHub Actions workflows. The CI workflows call `gcloud storage cp` directly rather than `download_from_gcs.py` (that script is for local/manual use).

### CI/CD Schedules

| Workflow | Runs | What it does |
|---|---|---|
| `collect_news.yaml` | Daily cron 00:30 UTC (09:30 KST), or `workflow_dispatch` | Collect + upload to GCS; Mondays: start `generate_newsletter` |
| `generate_newsletter.yaml` | Started by Monday's collect (or `workflow_dispatch`) | Download → generate → evaluate with judge (writes `summary.json`) → edition checks (writes `gate.json`) → upload → start `send_mail` if `send_after`; evaluate and checks are `continue-on-error`, so neither can stop the send |
| `tests.yaml` | Every push / pull request | `python -m unittest discover -s tests` with placeholder secrets |
| `smoke_test.yaml` | After `tests` passes on a push to `main` (or `workflow_dispatch`) | Collect → generate → evaluate → checks for Arsenal only, then `send_mail.py --test` to `ALERT_EMAIL`. Uploads nothing to GCS, never reads the subscriber sheet; a few cents of OpenAI per merge; emails the operator on failure |
| `send_mail.yaml` | Started by generate (or `workflow_dispatch` with `dry_run`) | Download this week's newsletters → send via SMTP → upload `sent.json` |

The rest of the chain follows `collect_news` within ~20 minutes. Monday 00:00 UTC (09:00 KST) is the end of the edition week (`edition.py`), so the trigger must stay after it unless editions are anchored on KST first. Each workflow emails the operator on failure (`notify.py`). A manual `generate_newsletter` run does not email subscribers unless `send_after` is ticked.

### GitHub Secrets Required

`OPENAI_API_KEY`, `GCP_SA_KEY`, `GOOGLE_CLOUD_EMAIL`, `GOOGLE_CLOUD_SPREADSHEET_URL`, `SMTP_USERNAME`, `SMTP_PASSWORD` (optional: `ALERT_EMAIL`)

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
