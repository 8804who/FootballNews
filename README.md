[한국어](README.ko.md) | English

# Football News

Collects football club news, generates a newsletter, and sends it to subscribers weekly.

## Workflow

1. **Collect** — Collect match reports and transfer news for configured Premier League clubs daily, from FotMob and Google News RSS.
2. **Generate** — Generate a newsletter per club weekly, based on the last 7 days of collected data plus the generation day itself (which covers Sunday-night UK matches, i.e. Monday dawn in Korea).
3. **Evaluate** — Evaluate the generated newsletter against source data.
4. **Send** — Send the newsletter to subscribers.
5. **Publish** — Generate and publish a dashboard for subscriber counts, workflow status, and evaluation score history.

## Architecture

```
1) collect_news.py  (daily, 00:30 UTC)
     ├─ scrappers/fotmob.py    → renders FotMob match pages with Playwright + hits its API
     │                            → parses events/stats/substitutions/goals/cards
     └─ scrappers/news_rss.py  → parses Google News RSS
     → writes team_daily_report_{team}_{matches,transfers}.md / team_daily_report_{team}.md
     → uploads to gs://my-football-news/football-news/datas/{fotmob,news_rss}/YYYYMMDD/

2) generate_newsletter.py  (weekly, Mon 01:00 UTC)
     downloads the last 7 days of fotmob + news_rss data from GCS, plus the
     generation day itself (collect_news.py names its output folder by the day
     it runs, not the match date, so Monday's run — which also sweeps up
     Sunday-night UK matches, i.e. Monday dawn KST — lands in the Monday folder)
     └─ summarizers/llm.py (LLMSummarizer)
          → LangChain FewShotPromptTemplate + ChatOpenAI
          → generates a newsletter per team based on prompt.yml (system/section
            prompts) and example.yml (few-shot examples)
     └─ evaluate/evaluate_main.py scores the newsletter against the fotmob source data
     → uploads newsletter/ and evaluation/ to GCS

3) send_mail.py  (weekly, Mon 02:00 UTC, ~1h after generate)
     downloads this week's newsletter/ from GCS
     ├─ google_sheet_parser.py      → pulls per-team subscriber emails from the
     │                                 "신청자 목록" (signup list) worksheet
     └─ email_sender/smtp_sender.py → sends via Gmail SMTP

4) generate_dashboard.py  (triggered after collect_news / generate_newsletter finish)
     aggregates subscriber counts, workflow run history, and evaluation score history
     └─ dashboard/render.py → generates dashboard → deployed to GitHub Pages
```

## Code structure

```
config.py               Config

scrappers/
  fotmob.py              Extracts events/stats/substitutions/goals/cards from
                          FotMob match pages via Playwright.
  news_rss.py             Google RSS news collection
  fbref.py, fpl.py         Unused

summarizers/
  llm.py                  Newsletter generation

evaluate/                 Scores generated newsletters against fotmob source data
    score_accuracy.py        30% — do in-newsletter scores match the source?
    section_completeness.py  20% — are all 4 required sections present & valid?
    llm_drift.py              15% — did the model drift into chatbot mode?
    hallucination.py          25% — are there player names not in the source?
    language_compliance.py    10% — is the Korean character ratio above 80%?
  utils.py                 Shared date parsing / lookback-window logic

email_sender/
  email_sender.py          EmailSender abstract class
  smtp_sender.py            Gmail SMTP + markdown-it-py to convert Markdown to
                          HTML before sending

dashboard/
  render.py                Renders collected stats (subscribers, workflow
                          status, evaluation history) into the dashboard

tests/                    Unit tests
```

### Configuration layers

`config.py` reads the following files, in order, at import time, and exposes them as constants.

| File | Purpose |
|---|---|
| `api.yml` | API keys/credentials (GitHub Secrets used in GitHub Actions) |
| `setting.yml` | Target teams and the LLM model to use |
| `prompt.yml` | LLM system prompt and per-task prompts |
| `example.yml` | Few-shot examples for newsletter writing |
| `teams.yml` | FotMob team info (ID, name) mapping |

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

# Generate newsletter
python generate_newsletter.py

# Evaluate
python evaluate/evaluate_main.py
python evaluate/evaluate_main.py --date 20260306
python evaluate/evaluate_main.py --team Liverpool

# Send newsletter
python send_mail.py

# Generate dashboard
python generate_dashboard.py
```

## Automation

| Workflow | Schedule | Does |
|---|---|---|
| `collect_news.yaml` | Daily 00:30 UTC (09:30 KST) | Collect + upload to GCS |
| `generate_newsletter.yaml` | Monday 01:00 UTC (10:00 KST) | Download 7 days → generate → evaluate → upload |
| `send_mail.yaml` | Monday 02:00 UTC (11:00 KST) | Download this week's newsletters → send |
| `dashboard.yaml` | After `collect_news`/`generate_newsletter` finish | Rebuild + deploy the status dashboard |

Required GitHub Secrets: `OPENAI_API_KEY`, `GCP_SA_KEY`, `GOOGLE_CLOUD_EMAIL`, `GOOGLE_CLOUD_SPREADSHEET_URL`, `SMTP_USERNAME`, `SMTP_PASSWORD`.
