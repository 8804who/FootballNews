# TODOs

DX follow-ups from a 2026-08-08 review. None of these block the pipeline today;
each is a recovery-speed or reliability improvement for whoever (future-you)
touches this repo next.

## 1. `--team` filter on collect_news.py / generate_newsletter.py

**What:** Add a `--team` flag so either script can run for a single team
instead of always looping over all of `setting.yml`.

**Why:** `evaluate/evaluate_main.py` already supports `--team Liverpool` for
ad-hoc checks. The two scripts most likely to be run while debugging a single
team's newsletter (collect + generate) don't — you have to temporarily edit
`setting.yml` and remember to revert it.

**Context:** Both scripts currently do `for team in TEAMS:` with no filtering.
Mirror `evaluate_main.py`'s `argparse` pattern (`--team`, partial match ok).

**Depends on / blocked by:** Nothing.

## 2. Error handling in send_mail.py's send loop

**What:** Wrap `smtp_sender.send_email(...)` in `send_mail.py`'s subscriber
loop (send_mail.py:44-46) in try/except: log the failure (team + email), keep
going to the next subscriber, and print a final summary of any failures.

**Why:** Today, one bad address or a dropped SMTP connection mid-run crashes
the whole script. Subscribers after the failure point never get sent, there's
no record of who already got the email, and a naive re-run after fixing the
issue re-sends duplicates to everyone before the crash point. Worst-case
combination for an email tool: silent partial send + duplicate risk on retry.

**Context:** `email_sender/smtp_sender.py`'s `send_email` calls `smtplib`
directly with no retry/backoff — a raised exception there currently
propagates straight out of the loop.

**Depends on / blocked by:** Nothing.

## 3. Document "how to add a team" in the README

**What:** Add a short README subsection: adding a team means editing both
`setting.yml` and `teams.yml`, and `teams.yml` needs a FotMob numeric team ID
— explain where to find one (e.g. the team's FotMob URL,
`fotmob.com/teams/<id>/...`).

**Why:** `teams.yml` exists specifically to support more teams later, but
there's currently zero documentation on how to get the one non-obvious piece
(the FotMob ID) — future-you would have to reverse-engineer it from FotMob's
network requests.

**Depends on / blocked by:** Nothing. Docs-only.

## 4. `--dry-run` flag for send_mail.py

**What:** Add a `--dry-run` flag that prints what would be sent (team,
recipient, subject) instead of calling `smtp_sender.send_email(...)`.

**Why:** Right now the only way to verify a fix to the send path works is to
actually email real subscribers. Debugging a broken Monday send — the
scenario this whole pipeline exists to avoid — currently requires either
risking a real send or manually editing the subscriber sheet to test.

**Depends on / blocked by:** Pairs well with #2 (both touch the send loop).

## 5. Test coverage for scrappers/fotmob.py

**What:** Add test coverage for `scrappers/fotmob.py` (~430 lines, the most
complex component — Playwright scraping of a third-party site's rendered
DOM). `tests/` currently only covers `news_rss.py`.

**Why:** If FotMob changes their page markup, nothing catches it until
Monday's newsletter is visibly wrong or empty. A fixture-based test against a
saved FotMob HTML snapshot, or a lightweight schema-shape assertion on the
scraper's output, would catch breakage before it reaches subscribers.

**Depends on / blocked by:** Nothing, but needs a decision on fixture
strategy (saved HTML snapshot vs. live-hitting FotMob in CI — the latter is
flaky and not recommended).

## Deferred from CONTENT_PLAN.md (2026-10-31 /autoplan)

- **Headline as the email subject + a preheader** built from code facts ("2위 · 다음 경기 11/5(목) 새벽 5시 Slavia Prague 원정"). Wait for two live editions on the new headline rule.
- **Match headline sees the week's top news**: the Nov 2 Arsenal preview headlined Gyökeres's equaliser, not the League Two upset; the match call never sees the BBC summary that says "biggest upset in the competition's history".
- **Player positions on first mention** for new fans (FotMob squad data), if it doesn't make the copy clunky.
- **Send time** before work (Cloud Scheduler, edition window anchored on KST): the copy no longer promises 출근길/점심 until this is done.
- **"3 identical endings in a row" got worse** (2.4 → 4.1 per edition): 합쇼체 endings repeat by nature, but try a rhythm example in example.yml.
- **`signup_url`** in setting.yml is still empty, so forwarded readers can't subscribe.
