# FootballNews — Product Plan

**Date:** 2026-10-29 (progress update 2026-10-30) · **Stage:** live MVP — 12 subscribers, 6 clubs, 28 consecutive Monday sends · **Owner:** 8804
**Method:** PM frameworks (Product Strategy Canvas, user research synthesis, North Star framework, outcome-based roadmap). They were applied to the codebase, the live dashboard, GitHub Actions history, and real editions and eval reports in GCS.

> **Confidence:** there is no reader research or engagement data yet, so everything about subscribers is a **hypothesis** to validate (§7). Everything about the pipeline is **verified** against data (evidence log at the end).

---

## TL;DR

1. **The machine works. Trust was the bottleneck — and the "Now" fixes are now in** (see [Progress](#progress--2026-10-30)).
   - 28 Mondays in a row without a failed send is a real achievement.
   - Over Aug–Oct, readers got:
     - another club's news: fake De Bruyne/Anderson/Guardiola items in about 14 editions, which the model copied from a few-shot example;
     - a repeat of the previous week's match;
     - an edition missing the whole weekend round;
     - one result printed backwards.
   - All of these now have a fix in code, plus a pre-send check that holds a club's email if anything like it happens again.
2. **The eval caught the leak every week, and nobody could see it.**
   - It flagged "Kevin De Bruyne" in Arsenal, Liverpool and Chelsea editions.
   - Those flags sat next to false alarms like "Sky Sports", "Champions League" and "Man Utd".
   - The score check failed whenever the model wrote "Man City", and no edition ever met the Korean-ratio target.
   - Both problems are now fixed and calibrated against 72 real editions.
3. **You measure the output, not the outcome.** You know each edition's eval score to one decimal place. You don't know whether any of the 12 subscribers opens it. This is still open; it's the Next theme.
4. **The plan:**
   - **Now ✅:** make every edition correct, complete and controllable.
   - **Next:** make it worth opening on Monday morning, and make that measurable (1–2 months).
   - **Later:** make it shareable and scalable, but only once engagement is proven.
5. **Two decisions are still yours:** what success means by May 2027, and the send time (§8).

---

## Progress — 2026-10-30

Every "Broken" item in §1 that code can fix is now fixed and verified. The changes sit in the working tree and aren't committed yet. The workflow changes take effect once they're pushed to `main`.

### Status of the broken items

| # | Problem | Status | What fixed it |
| --- | --- | --- | --- |
| R1 | Other clubs' news in your club's edition | ✅ Fixed at the cause | The model was answering a few-shot *example* instead of the real input, because everything was one long string. Now the examples are separate, labelled chat turns, and all of them are fictional. The gate holds any edition containing an example name, or a name found only in another club's sources. |
| R2 | Weekend round missing | ✅ Fixed | Collection looks back 3 days. Monday's newsletter only starts after a successful collection. The gate holds a club if FotMob's fixture list shows a finished match that was never collected. |
| R3 | Last week's match shown again | ✅ Fixed | Editions pick matches by kickoff time (Monday 00:00 → Monday 00:00 UTC), not by collection folder. The gate holds any scoreboard row that isn't in the week's source. |
| R4 | Old news presented as current | ✅ Fixed for new data | RSS now stores publish times. Headlines from outside the week, and previews of matches that have already been played, are dropped. Older files fall back to folder dates. |
| R5 | Invented precision | ✅ Fixed | No percentages. Each item carries its source type (보도 / 가십). Club landing pages and live blogs are filtered out before the model sees them. |
| R6 | Nothing to click | ✅ Fixed | The model cites headlines as `[N1]`; code swaps the tags for links. The gate checks that every link belongs to this club's headlines. |
| R7 | Arrives in the afternoon | 🟡 Partly | Sending now starts right after generation, removing the fixed 1–1.5 h gaps. The chain still starts whenever GitHub fires the cron (about 5 h late). The real fix, an external trigger, is in Next and depends on your send-time decision. |
| R8 | No unsubscribe, unclear sender | ✅ Code done · ⏳ form edits are yours | The sender shows as "FootballNews". Every email has a footer (why you get this · 수신거부 · 팀 변경 · 의견), a `List-Unsubscribe` header and a plain-text part. Addresses in a `수신거부` worksheet are never emailed. |
| R9 | Silence after sign-up | 🟡 Partly | Team answers resolve through aliases ("TottenhamHotspur", "Spurs", "토트넘"). An answer that matches no club is reported instead of silently dropped. The welcome email is still in Next. |
| O1–O3 | Eval false alarms | ✅ Fixed | Score matching understands aliases. Competitions, outlets and our own clubs no longer count as people. A name followed by a Korean particle is read whole. The Korean ratio is measured without the English names the style guide requires (target 95%). |
| O4 | Eval never gates | ✅ Fixed | `evaluate/gate.py` runs yes/no checks before sending. A club that fails is held, and you get an email explaining why. |
| O5 | A green job doesn't mean delivered | ✅ Fixed | `send_mail` fails the run on any failed send or missing file, instead of sending a blank email. `sent.json` makes a re-run skip everyone who already got the edition. |
| O6 | Workflows chained by the clock | ✅ Fixed | collect → (Mondays) generate → send, each started by the one before. |
| O7 | No alerting | ✅ Fixed | Every workflow emails you when it fails (`notify.py`). The gate emails you when it holds a club. |
| O8 | Docs and dashboard drift | ✅ Fixed | The dashboard legend is built from the real weights, news grounding is shown, and its eval now loads RSS. README, README.ko and CLAUDE.md are updated. |

### Found while fixing

| # | Finding | Status |
| --- | --- | --- |
| N1 | **Subscriber addresses were printed in public workflow logs.** The repo is public, and `send_mail` logged "Sent to …" on every run (36 runs since April). | ✅ Logs now show masked addresses (`j***@gmail.com`) · ⏳ old logs still contain them (see "What's left" item 2) |
| N2 | The few-shot leak was far wider than one edition. The old example claimed De Bruyne "officially" joined Real Madrid on 2026-03-31, plus Elliot Anderson and Pep Guardiola rumors. It reached about 14 editions of Arsenal, Chelsea, Liverpool, Man United and Spurs between Aug 20 and Oct 19 — Chelsea's 4 times. | ✅ Fixed at the cause (R1) |
| N3 | A result went out reversed. Chelsea won 3–2 at Fulham (Aug 31), but the edition printed "Chelsea vs Fulham 2-3 — 초반 리드에도 종료까지 지키지 못했습니다", i.e. a loss. | ✅ The prompt now requires Home vs Away in the source's order, and the gate catches a reversed score |
| N4 | Re-running generate on the same day would have nested the files under `newsletter/{date}/{date}/` in GCS, so `send_mail` would have mailed the old copy. | ✅ The upload now targets the parent prefix |

### How it was verified

- **59 unit tests** (`python -m unittest discover -s tests`; no network, no email). They cover:
  - edition windows, dedupe and backfill;
  - news filtering and citation links;
  - alias matching;
  - every gate check;
  - the send loop: holds, unsubscribes, duplicates, retries and dry run;
  - the email headers.
- **Replay of 72 real editions** (Aug 17 – Oct 26) through the new evaluator and gate:
  - The gate would have held 35 of them. Every hold I could check was a real defect: 28 repeated matches, 7 matches missing from the scoreboard, 1 reversed result, plus the few-shot leaks and players from those stale repeats. One flag couldn't be checked, because my download didn't reach that edition's sources.
  - Score accuracy averages 89.6%, with 49 of 56 editions at 100%. On Oct 26 alone it had read 40%.
  - The hallucination rate is 17.7%, down from about 48%.
  - The Korean ratio has a median of 99.6%. All 4 editions below 95% are real drift, e.g. the untranslated "could be forced to accept small fee for wantaway teen".
- **Regenerated the week of Oct 12–18** for all six clubs with the new pipeline:
  - Result: 0 holds, 0 warnings, and 100% on every eval metric.
  - The first attempt, still using the one-string prompt, copied the fictional example into 2 of 3 clubs, and the gate held both.
  - A later attempt pasted English headlines as titles. The recalibrated Korean metric flagged it (71%), and a prompt rule fixed it.
  - These are the same weeks that went out with leaked City rumors.
- **Live collection** for Arsenal:
  - The 3-day lookback caught the Oct 27 Fleetwood cup tie.
  - The fixture list was saved (53 fixtures; next is Liverpool–Arsenal on Nov 1).
  - RSS lines now carry publish times, and landing pages are gone.
- **Dry run against the real sheet:** 12 subscribers resolved (2/1/1/3/2/3), including "TottenhamHotspur". Nothing was sent.
- **Email rendered at phone width:** the footer and source links use existing DESIGN.md tokens only (decision logged in DESIGN.md).

### What's left for you

1. **Review and push.** Nothing is committed, and the workflow changes only run once they're on `main`. The first chained run is Monday Nov 2: check the summary of the "Check each edition before sending" step.
2. **Delete the old `send_mail` logs that contain addresses** (36 runs). This can be done with `gh`; it can't be undone, and it touches nothing else.
3. **Sign-up form (Google Form):**
   - make the team question a dropdown with exactly the six names in `setting.yml`;
   - add the consent notice below;
   - put the form link in `setting.yml` → `newsletter.signup_url`, which adds 팀 변경 to the footer.
4. **Unsubscribes:** by default the footer's 수신거부 link emails you. When one arrives, add the address to a worksheet named `수신거부` in the subscriber spreadsheet (create it the first time). Optionally, make an unsubscribe Form and set `newsletter.unsubscribe_url`; `{email}` is filled in automatically.
5. **Optional:** add a GitHub secret `ALERT_EMAIL` if alerts should go somewhere other than the sending Gmail account.

Consent notice draft, for the form description or a required checkbox:

> [개인정보 수집·이용 안내] 수집 항목: 이메일 주소, 응원 팀 · 이용 목적: FootballNews 주간 뉴스레터 발송 · 보유 기간: 수신거부(구독 해지) 시까지 · 동의를 거부할 수 있으며, 거부 시 뉴스레터를 받을 수 없습니다.

---

## 1. Where you are (diagnosis, 2026-10-29)

This section records the state before the Oct 30 fixes; their status is in [Progress](#progress--2026-10-30).

### Working — keep it

| What | Evidence |
| --- | --- |
| Delivery never skipped | `send_mail` succeeded on all 28 scheduled Mondays since 2026-04-20 |
| Collection runs daily | `collect_news` ran on 224 distinct days since 2026-03-19, with no gap over 2 days and 6 failures in total |
| People sign up without marketing | 6 subscribers (Aug 7) → 12 (Oct 29): Arsenal 3 · Tottenham 3 · Man United 2 · Man City 2 · Liverpool 1 · Chelsea 1 |
| The voice | The May design audit graded content **A**. Headlines like "Eze의 깜짝 투입, Rice의 극장 응답" are what a reader repeats at lunch |
| Running cost ≈ 0 | About 12 LLM calls a week on gpt-5-mini; Actions are free on a public repo; GCS costs pennies |
| Instrumentation habit | Eval harness, dashboard, design system, TODOS. That's rare for a side project |

### Broken — readers can see it

| # | Problem | Evidence | Root cause |
| --- | --- | --- | --- |
| R1 | **Other clubs' news in your club's edition** | Arsenal, Oct 19: "Kevin De Bruyne … 공식 처리", plus Elliot Anderson and Pep Guardiola rumors. None of them appear in Arsenal's FotMob/RSS data. The same items reached about 14 editions across 5 clubs (N2) | The model answered the few-shot example instead of the real input. Real names in the example made it look plausible |
| R2 | **Weekend round missing** | GCS has no `fotmob/` or `news_rss/` folder for 20261025 or 20261026. The Oct 26 edition only covers matches played Oct 18–21, and Chelsea's has no match section | `collect_news` failed two days running. It only looked back one day, so nothing backfilled the gap |
| R3 | **Last week's match shown again** | "Nottm Forest vs Arsenal 0-1" and "Leeds vs Man United 1-1" appear in both the Oct 19 and the Oct 26 editions. In the replay this happened in 28 rows | The window was today-7 to today inclusive, which is 8 daily folders, so the previous Monday's folder landed in both editions |
| R4 | **Old news presented as current** | Man City, Oct 26: "Erling Haaland 출전 불투명", from a pre-match BBC headline about the game the same edition reports as a 5-1 win | Headlines reached the LLM without publish times |
| R5 | **Invented precision** | Chelsea, Oct 26: "Reece James 약 3개월 결장(확정) — 가능성 99%". BBC's generic "Transfer news" page became a "50%" rumor | The prompt asked the model to make up a 0–99% likelihood |
| R6 | **Nothing to click** | Sources appeared as "(Sky Sports)", although the RSS URLs were collected | Prompt and output schema |
| R7 | **Arrives in the afternoon** | Scheduled for 11:00 KST. Sep–Oct send jobs started between 15:58 and 17:34 KST | GitHub cron runs about 5 hours late |
| R8 | **No unsubscribe, unclear sender** | No footer and no `List-Unsubscribe`. From was the bare Gmail address | Email template |
| R9 | **Silence after sign-up** | The first email arrives the next Monday. A team answer that differed from `setting.yml` never matched; the sheet stores "TottenhamHotspur" | No welcome flow; matching only ignored spaces and case |

### Broken — only you can see it

| # | Problem | Evidence |
| --- | --- | --- |
| O1 | The score check failed correct scores | Oct 26 scored 0% for Man City, Man United and Tottenham, because the model wrote "Man City / Man United / Tottenham" |
| O2 | The hallucination check flagged things that aren't people, and names that are grounded | "Sky Sports", "Champions League", "Man Utd", "Paper Talk"; also Haaland and De Zerbi, both in that week's RSS |
| O3 | A Korean-ratio target nobody could hit | 0 of 22 editions reached 80%. English proper nouns are mandatory, so it was structurally out of reach |
| O4 | The eval neither improved nor gated | The weekly score stayed between 64.0% and 80.4% with no trend. The evaluate step was `continue-on-error` |
| O5 | A green job didn't mean delivered | `send_mail.py` caught errors per recipient, so the job passed even if every send failed |
| O6 | Workflows were chained by the clock | Three independent crons, each firing about 5 hours late |
| O7 | No alerting | The Oct 25–26 failures were found after the edition had already gone out |
| O8 | Docs and dashboard drift | The legend, README and CLAUDE.md showed the old five-metric weights |

---

## 2. Your subscribers — who they are and what they need

**Data:** sign-up counts per club, the persona in `prompt.yml`, the May design audit, and 13 weeks of editions. There are no interviews, surveys or engagement data, so treat these personas as hypotheses.

### Personas

#### P1 · 출근길 라이트팬 — "새벽 경기는 못 봐요. 그래도 월요일엔 같이 얘기하고 싶어요."

- **Who:** an office worker in their 20s or 30s who follows one club and rarely watches live. UK kick-offs land between 20:30 and 05:00 KST.
- **JTBD:** When I wake up on Monday having missed the weekend's match, I want an accurate, fun three-minute rundown of my club, so I can join the conversation at work or in the group chat.
- **Pains:** dawn kick-offs; scattered, clickbait-y portal headlines; noisy communities; English sources take effort.
- **Gains:** a headline worth repeating, short one-liners, and the next kick-off in KST.
- **Behavior:** reads on a phone during the commute or a break. Skims the headline and scoreboard, maybe one story.
- **Prevalence:** this is who `prompt.yml` is written for, and probably most of the 12 (unverified).

#### P2 · 새벽 직관러 — "결과는 이미 알아요. 루머 중에 뭐가 진짜인지 알려주세요."

- **Who:** watches live and spends time in communities (에펨코리아, 해외축구 갤러리) and on FotMob.
- **JTBD:** When my feed fills with translated tabloid rumors, I want only the credible ones with their source, so I don't get fooled.
- **Pains:** rumor noise and mistranslation.
- **Gains:** rumors labeled by source, injury news, and what's coming next.
- **Behavior:** skips the recap and goes straight to 이적 & 뉴스.
- **Risk:** the reader most likely to notice wrong or repeated results, because they watched the match.

#### P3 · 입덕 중인 뉴비 — "좋아하게 된 지 얼마 안 돼서 선수 이름도 잘 몰라요."

- **Who:** started following the club recently, through a friend, a Korean player, FPL or a viral moment.
- **JTBD:** When I'm new to a club, I want each week explained with context on who's who, so I can enjoy the matches and feel part of the fandom.
- **Gains:** player intros and storylines that carry on week to week. The `prompt.yml` rule "never skip context on who a player is" already serves them.
- **Behavior:** reads everything, and is the most likely to forward it.

#### P4 · 지인 구독자 (unexpected) — "만든 사람이 친구라서 구독했어요."

- **Who:** subscribed because they know you. At 12 subscribers, that's probably several of them.
- **Why it matters:** their opinions will be kind, so weight their **behavior** (clicks, replies, forwards) over what they say. **The first 50 subscribers who don't know you are the real product test.**

### Segments (behavioral)

| Segment | Size now | Primary job | Fit today | Value | Growth |
| --- | --- | --- | --- | --- | --- |
| Catch-up readers (P1) | Most of 12 (hyp.) | The Monday rundown | Good now that matches are complete and appear once | **Highest** | High: the biggest pool |
| Rumor filterers (P2) | A few (hyp.) | Credible rumors only | Better: source labels and links, no invented % | Medium | Medium |
| New fans (P3) | A few (hyp.) | Context and storylines | Good | Medium | **Highest**: they share |
| Fans of clubs you don't cover | 0 (not offered) | The same jobs | None | ? | Unknown; measure with a waitlist |

### Customer journey

| Stage | Touchpoint | Emotion | Pain (evidence) | Opportunity |
| --- | --- | --- | --- | --- |
| Awareness | You or a friend shares a Google Form link | Curious | Nothing to show them: no sample, no archive, no landing page | A public archive on the GitHub Pages site you already deploy |
| Consideration | Two-question form (team, email) | Unsure | No sample, no promise about cadence or content, no privacy notice | A sample edition, "매주 월요일 아침, 3분", consent text (draft in Progress) |
| Sign-up | Form → "신청자 목록" sheet | Done… | 0–7 days of silence | An instant welcome email with the latest edition; a fixed dropdown |
| First edition | Monday afternoon, a date-stamp subject | "What is this?" | No hook; risk of landing in Promotions or Spam | Sender name and footer ✅; still to do: headline as the subject, a preheader, delivery before work |
| Reading | Masthead → headline → match story → scoreboard → 이적 & 뉴스 | Delight at the voice | Previously repeats, gaps, made-up percentages and nothing to click ✅ fixed; nothing about next week yet | A 다음 경기 (한국 시간) section (the fixture list is already saved) |
| Retention | Weekly | Habit, or drifting away | Couldn't leave ✅ fixed; can't add a club | Footer: 수신거부 · 팀 변경 · 의견 ✅ |
| Advocacy | Forward or screenshot | Pride | No share link and no subscribe call-to-action | "친구에게 공유하기" → an archive page with sign-up |

**Biggest drop-offs:** the silent first week, the first visible error, and having no way to share.
**Moment to amplify:** the headline and one-liners. That's the "social currency" P1 signs up for.

---

## 3. Product Strategy Canvas

### 1 · Vision

> **새벽 경기를 놓쳐도, 월요일 대화에선 빠지지 않게.**
> Every Korean Premier League fan, however busy, starts the week knowing what happened to their club and what's next. Accurate, in Korean, in three minutes.

### 2 · Target segments

| Segment | Size | Pain | Current alternative | Priority |
| --- | --- | --- | --- | --- |
| Light fans who don't watch live (P1) | Large (hyp.) | Medium–high: time zone, fear of missing out | Naver/Daum sports, YouTube highlights, group chats | **1 — design for them** |
| New fans (P3) | Medium | High: no context | YouTube explainers, friends | 2 |
| Die-hards (P2) | Medium | Low for results, medium for rumors | Communities, FotMob, X | 3 — serve them through the rumor section; don't build for them |

Not serving, for now:

- Tactics readers: The Athletic and analysis YouTubers do it better.
- Fantasy and betting users: they need real-time line-ups, and betting-adjacent content is legally sensitive in Korea.
- People who want live scores: apps already win that.
- Other leagues.

### 3 · Pain points → value

| Pain | Cost today | Value created |
| --- | --- | --- |
| Kick-offs at 20:30–05:00 KST | Missing the match, or losing sleep | A Monday catch-up plus the next kick-off in KST |
| Rumor noise and mistranslation | Time, and getting fooled | Rumors from BBC, Sky and The Athletic only, labeled and linked |
| English-first coverage | Effort, so they skip it | Casual Korean with context on each player |
| Being left out | Silence at Monday lunch | A headline and one-liners worth repeating |

### 4 · Value propositions

- **P1:** When I've missed the weekend's matches, I want a trustworthy three-minute rundown of my club in Korean, so I can talk about it on Monday.
- **P3:** When I'm new to a club, I want each week explained with context on who's who, so I can feel part of the fandom.
- **P2:** When rumors flood my feed, I want only the credible ones, linked to the source, so I know what's real.
- **Positioning line:** *"내 팀 소식만, 믿을 만한 출처로, 월요일 아침 3분."* The "믿을 만한" claim is now backed by source links and the pre-send checks; earn it for a few weeks before saying it publicly.

### 5 · Strategic trade-offs

| We choose | Over | Because |
| --- | --- | --- |
| A weekly digest | Real-time alerts | Apps already win real-time. The weekly catch-up is the unmet job, and it keeps ops tiny |
| One club per edition | League-wide coverage | Fandom is organized around clubs, and relevance drives opens |
| Correct and complete | More sections | One wrong or stale item costs more trust than a new section earns |
| Credible outlets only | More rumors | Communities already overflow with tabloid rumors; curation is the value |
| A light, witty voice | Tactical depth | The target is light fans, and depth is covered elsewhere |
| Email | An app or KakaoTalk (for now) | Zero distribution cost and nothing to install. Revisit if growth stalls |
| Automation gated by checks | Fully hands-off, or fully manual | Send automatically when the checks pass; hold and alert you when they fail (now implemented) |
| Free | Paid or sponsored | There's no retention evidence yet, and ads bring 정보통신망법 §50 obligations |

### 6 · Key metrics (details in §4)

- **North Star:** Weekly Engaged Readers.
- **Inputs:** active subscribers, on-time complete editions, error-free editions, edition pull.
- **Health:** unsubscribe rate, spam complaints, cost per edition, and your own ops minutes per week.

### 7 · Growth engine

- **Now:** your network, plus a "friend forwarded this? 구독하기" line. It costs nothing.
- **Next:** one public archive page per edition, with OG tags so KakaoTalk and Threads previews look right, and a subscribe button on every page.
  - The loop: a reader shares, a friend reads the archive page, the friend subscribes.
- **Later:**
  - Post the week's edition in club fan communities (네이버 카페 fan cafés, 에펨코리아, 해외축구 갤러리), following each one's self-promotion rules.
  - Add clubs when the waitlist shows demand.
- **Economics:** content cost scales with clubs, not subscribers.
  - A new reader costs about ₩0.
  - A new club costs two LLM calls a week plus a few minutes of scraping a day.

### 8 · Core capabilities

| Capability | Build / Buy / Partner | Investment | When |
| --- | --- | --- | --- |
| Match data | Build (FotMob scraping), plus a bought fallback (API-Football; the IDs are already in `teams.yml`) | Medium | Backfill ✅; fallback Later |
| News intake | Build (Google News RSS, 3 outlets) | Low | Timestamps, links ✅ |
| Generation | Build (LangChain, chat-format few-shot) | Low | ✅ restructured; Next: 다음 경기 section |
| Quality gate | Build (calibrated eval, hard checks, hold and alert) | Medium | ✅ |
| Delivery | Gmail SMTP → buy an ESP API | Low → Medium | Next (tracking), Later (lists) |
| Subscriber management | Google Form and Sheet → ESP lists | Low | Unsubscribe ✅; migrate Later |
| Engagement measurement | Build a minimal version (feedback links), then buy (ESP analytics) | Low | Next |
| Archive and landing page | Build (GitHub Pages is already live) | Low | Later |
| Ops and alerting | Build (a chained workflow and email alerts) | Low | ✅ |

### 9 · Defensibility

Honestly, there isn't much yet, and that's normal at 12 readers. Someone could clone the pipeline in a weekend.

What you can own:

1. **The list.** An email audience you own is the real asset. Protect it with consent, good deliverability and clean unsubscribes.
2. **A track record of being right.** "Never wrong, never stale" compounds over time, while competitors that publish raw LLM output keep making the errors listed in §1.
3. **The voice.** The tone in `prompt.yml` is a brand.
4. **Labeled data.** Every edition you check by hand becomes ground truth for the eval. A season of that is a dataset nobody else has.

Not a moat: the model, the scraping, the design.

### Strategic risks

1. **Trust collapses.** A fan who watched the match spots a wrong, repeated or missing result and quietly stops opening. Now guarded by the pre-send checks; keep the gate precise so its holds stay credible.
2. **The source breaks.** FotMob scraping is unofficial and probably not permitted by their terms. A markup change or a block would kill the match section overnight. Fixture tests (TODOS #5) and an API fallback address this.
3. **Building blind.** Without engagement data, you'll keep polishing what you can measure (the eval) instead of what readers value. Interviews and feedback links in Next address this.

---

## 4. North Star framework

**Business game:** Attention (media). There's no revenue model yet, so the metric has to capture value delivered, not money.

### North Star: Weekly Engaged Readers (WER)

- **Definition:** unique subscribers who opened or acted on that week's edition within 7 days of the send. Acting means clicking a link, tapping 👍/👎 or replying. Exclude opens that Apple Mail Privacy Protection pre-fetches, where the ESP flags them.
- **Why:** it only grows when editions are accurate and relevant *and* reach people, which is the value you deliver.
- **Current:** unknown. Gmail SMTP can't measure it, so making it measurable is a Next deliverable.
- **Target:** at least 60% of active subscribers on a list this warm. Under ambition (b), 100 WER by the end of the 2026-27 season.

| Criterion | Pass? | Notes |
| --- | --- | --- |
| Expresses value | ✓ | Opening or acting means the edition was used |
| Leading indicator | ✓ | Engaged readers forward it and stay, and they're what a sponsor would pay for |
| Measurable | ✓ after Next | Feedback links now, ESP open and click tracking later |
| Understandable | ✓ | "How many people actually used this week's edition?" |
| Actionable | ✓ | Accuracy, timing, subject line and growth all move it |
| Not vanity | ✓ | Sign-ups that never engage don't count |
| Not gameable | Mostly | Clickbait subject lines could inflate opens; the counter-metrics below guard against that |

### Input metrics (reach × delivery × quality × pull)

| Input | How it moves WER | Current | Target |
| --- | --- | --- | --- |
| **Active subscribers**: not unsubscribed and not bouncing | It sets the ceiling | 12 | 30 by the end of Next, 100+ Later |
| **On-time complete editions**: % of club editions delivered by the promised time, with every finished match in the window, exactly once | The edition arrives when the reader needs it | Complete & once: guarded by the gate from Nov 2 · On time: 0 of 4 in October | 100% |
| **Error-free editions**: % with zero hard-check failures | It keeps trust | Now measured: `gate.json` per edition (35 of 72 past editions would have failed) | 100%, with a monthly check by hand |
| **Edition pull**: % of recipients who act (click, 👍/👎, reply) | It shows the edition was worth reading | Unknown | Set after a 4-week baseline |

```text
                      Weekly Engaged Readers
        ┌───────────────┬───────────┴──────────┬────────────────┐
 Active subscribers  On-time complete    Error-free         Edition pull
 · welcome email     · chained workflow ✅ · alias-aware eval ✅ · 다음 경기 (KST)
 · share CTA/archive · kickoff windows ✅  · hard gates ✅      · headline subject
 · clean unsubscribe ✅ · before-work send · hold & alert ✅    · links ✅, 👍/👎
```

### Counter-metrics

| Metric | Protects against |
| --- | --- |
| Unsubscribes per edition (alert above 5%) | Clickbait and over-sending |
| 👎 share of feedback | Inflating clicks with low-value links |
| Bounce and spam-complaint rate | Deliverability getting worse |
| Your ops minutes per week (15 or fewer) | Fixes that make you the bottleneck |
| LLM cost per edition | Prompt bloat, or model upgrades that don't improve quality |

Rejected candidates:

- **Subscriber count:** a vanity metric.
- **Open rate alone:** Apple MPP inflates it, and you can't measure it today.
- **Eval score:** it measures output, not outcome. Keep it as a guardrail.
- **Revenue:** there is none, and it's a lagging indicator.

---

## 5. Outcome-focused roadmap

**Themes:** Trust → Pull → Reach. You can't grow what readers don't trust, and you can't improve what you don't measure.

### Now — Trust (✅ implemented 2026-10-30, live after push)

| Outcome | Success metric | What was built | Status |
| --- | --- | --- | --- |
| **Every finished match appears exactly once** | 3 editions in a row with 0 missing and 0 repeated matches, checked against FotMob | `edition.py` selects by kickoff time; 3-day lookback; FotMob fixture list saved daily; the chain only generates after a successful Monday collection | ✅ Built · measure from Nov 2 |
| **Nothing ships that the sources can't back** | 0 example, other-club or untraceable names, and 0 foreign links, in sent editions | Chat-format few-shot with fictional examples; `[N]` citations → links; `evaluate/gate.py` holds failing clubs | ✅ Built · replay: 35/72 past editions would have been held |
| **The eval number means something** | Metric verdicts agree with checked reality | Alias-aware scores, person-only names, particle-safe regexes, Korean ratio without required names, RSS in the dashboard eval | ✅ Calibrated on 72 editions instead of hand-labelling 18 |
| **Readers control their subscription** | Every email has a sender name, a line on why they get it, 수신거부 / 팀 변경 links; unsubscribes honored before the next send | Footer, `List-Unsubscribe`, plain-text part, `수신거부` worksheet filter, alias-matched team answers | ✅ Code · ⏳ form dropdown, consent text and `signup_url` are yours |
| **You hear about failures before readers do** | An alert within 1 hour of any failure | `notify.py` on every workflow failure and every hold; `send_mail` exits non-zero on any failed send; `--dry-run`; `sent.json` prevents double sends | ✅ Built · a separate dead-man's switch for "nothing ran at all" is still open |

### Next — about 1–2 months · Pull

| Outcome | Success metric | Key initiatives | Confidence |
| --- | --- | --- | --- |
| **It arrives when readers need it** | At least 90% of sends land between 07:00 and 08:30 KST on Monday | Trigger collect from Cloud Scheduler (you already use GCP) via `workflow_dispatch`; generate and send already follow automatically. · Collect around 05:30 KST, after Sunday's late UK matches. · Note: `edition.py` anchors the week on the run's UTC date, so a run before 09:00 KST Monday is still Sunday in UTC. Anchor on KST before moving the time. | High |
| **Readers can plan their week** | "다음 경기" appears in every in-season edition | Next fixtures in KST from `team_daily_report_{team}_fixtures.json`, already saved daily since Oct 30. | High |
| **More of them open it** | Open rate goes up against a 4-week baseline | Use the headline as the subject, e.g. `[Arsenal] Eze의 깜짝 투입, Rice의 극장 응답 — Bayern 원정 2-2`. · Add a preheader. | Medium |
| **Rumors keep earning trust** | 0 invented percentages; every news item linked; 0 stale items | Done: source labels, links and stale-preview filtering. · Still to do: a 부상 & 팀 뉴스 sub-section. · Done (Oct 30): the prompt × model A/B harness from your May 7 office-hours design (`evaluate/harness.py`), with token and cost tracking; the first comparison is in `WORK_REPORT.ko.md`. | High |
| **You know what readers value** | WER can be measured; at least 8 of the 12 subscribers interviewed | 15-minute interviews (§7). · 👍/👎 links to a prefilled form, and "이번 호 어땠나요? 답장 한 줄이면 충분해요". · An ESP API with open/click tracking behind the existing `EmailSender` ABC. | High |
| **New subscribers get value on day 0** | Every new sign-up gets the latest edition the same day | An Apps Script `onFormSubmit` trigger, or a scheduled `welcome.py`. `sent.json` already prevents duplicates. | Medium |

### Later — the rest of the season · Reach (start only if WER is at least 60% and unsubscribes stay low)

| Outcome | Success metric | Key initiatives | Dependencies |
| --- | --- | --- | --- |
| **Readers can share it** | At least 10% of sign-ups come through archive or share links | A public archive with one page per edition and OG tags. · A subscribe button on every page. · A 친구에게 공유하기 line in the email. | The Now gates (public errors stay online) ✅ |
| **Fans of other clubs can join** | Add a club once its waitlist reaches 5 | A waitlist question on the sign-up form. · `teams.yml` IDs + aliases, and the "how to add a team" docs (TODOS #3). | Reliability holding up per club |
| **Delivery scales** | Inbox placement holds and no sending limit is hit | Move subscriber lists into an ESP before about 200 subscribers; a personal Gmail account caps at roughly 500 recipients a day. · Korean platforms (e.g. Stibee, Maily) or developer ESPs (e.g. Resend, Amazon SES). · Your own domain with SPF, DKIM and DMARC. | Unsubscribe and consent ✅ |
| **Match data survives FotMob changes** | The edition still ships when scraping breaks | Scraper tests against saved pages (TODOS #5). · An API-Football fallback. | — |
| **(Optional) It pays for itself** | — | Only after about 1,000 engaged readers: a club-merch affiliate or a sponsor. · Ads bring §50 duties: a (광고) subject prefix, prior opt-in, sender details, a free unsubscribe, and re-consent every 2 years. | Ambition (b) |

### Transformation notes

| Original backlog item | Outcome it now serves | Why this framing |
| --- | --- | --- |
| Reliability fixes | Every match appears exactly once | "Fix bugs" never ends; "0 missing, 0 repeated" has a clear done state |
| Eval calibration | The eval number means something | The goal isn't a higher score; it's a score you can act on |
| Unsubscribe and compliance | Readers control their subscription | It's a trust and deliverability feature, not paperwork |
| Next-fixture section in KST | Readers can plan their week | It ties the feature to the time-zone pain |
| Source links | Rumors earn trust | Links are the mechanism; trust is the outcome |
| Feedback loop | You know what readers value | It creates the North Star measurement |
| Landing page, archive, referral | Readers can share it | Growth is the outcome; pages are one way to get it |
| More clubs | Fans of other clubs can join | Waitlist demand decides, instead of guessing |
| ESP migration | Delivery scales (lists), plus measurement (tracking) | Split in two: tracking is needed in Next; moving the lists only matters near the Gmail cap |

**What changed:** as a feature list, the backlog was a pile of chores ranked by whatever felt urgent. As outcomes, it becomes a sequence. "The eval number means something" moved to Now because every later quality decision depends on it, and it turned out to matter immediately: the recalibrated metrics caught two prompt regressions during the fix itself.

---

## 6. What you'll need, and what your subscribers need

### You

| Need | Why | Cost | Status |
| --- | --- | --- | --- |
| An alert channel | You find out about failures first | Free | ✅ Email via `notify.py` (optionally set `ALERT_EMAIL`) |
| An unsubscribe path, a footer and consent text | Trust, deliverability, and the notice-and-consent rules of 개인정보 보호법 (purpose, data collected, retention, right to refuse) | Free | ✅ Footer and filter · ⏳ consent text on the form (draft in Progress) |
| Ground truth for the eval | Calibrating the metrics | Time | ✅ Replay of 72 editions; label by hand monthly from now on |
| A 5-minute look whenever a club is held | You only review exceptions, not every week | Time | Ongoing |
| An external scheduler | GitHub cron runs about 5 hours late | Cloud Scheduler free tier | Next |
| An ESP account with an API and tracking | To measure the North Star now, and to manage lists at scale later | Free tier, then low $ | Next / Later |
| Your own domain | A branded sender and DMARC alignment on the ESP | About $10–15 a year | Later |
| A fallback match-data API | In case FotMob breaks | Free tier | Later |

*This isn't legal advice. For a free newsletter without ads, clear consent and an easy unsubscribe cover the basics. Any advertising brings 정보통신망법 §50 into play.*

### Your subscribers

| They need | Today | Status |
| --- | --- | --- |
| All of this week's results, each shown once | Kickoff-time editions; the gate holds gaps and repeats | ✅ |
| Only their club's news, and only what's true | Chat-format examples; the gate holds leaks | ✅ |
| To know who's sending and how to leave | Sender name, footer, List-Unsubscribe | ✅ |
| It on Monday morning | It arrives in the afternoon | Next |
| The next kick-off in Korean time | Fixture list saved, section not built | Next |
| To tell real news from rumor, and check it | 보도/가십 labels and source links | ✅ |
| To switch club or add one | Switch via footer once `signup_url` is set; adding needs multi-club support | ⏳ / Later |
| Something to say at lunch | The voice already delivers this; keep it | ✅ |

---

## 7. Validation plan — talk to your 12 subscribers (start this week; it's free)

Run 15-minute chats in the Mom Test style: ask about past behavior rather than opinions, and don't pitch.

1. "Last Monday, how did you find out how [club]'s weekend went?" Tests: what they actually use instead.
2. "Walk me through the last time you opened FootballNews. When was it, where were you, and which part did you read?" Tests: timing and which sections matter.
3. "Did you watch that match live? Did the newsletter tell you anything new?" Tests: P1 versus P2.
4. "Have you ever noticed something wrong or out of date in it? What did you do?" Tests: trust — the leaked rumors and the reversed Chelsea result went to real readers.
5. "Have you forwarded it to anyone or mentioned it? What happened?" Tests: advocacy.
6. "If it stopped arriving, what would you miss, and what would you use instead?" Tests: value.

Hypotheses to confirm or kill:

- Getting it on Monday morning matters to P1.
- People want the 다음 경기 section.
- P2 readers exist, and they read the rumor section.
- At least a third of readers would forward an edition to a friend.
- Someone noticed the wrong or leaked items, and what they concluded.

---

## 8. Decisions for you

1. **Ambition by May 2027.** Pick one:
   - (a) small and excellent, for about 50 people you know;
   - (b) a growing product with about 100 engaged readers;
   - (c) a portfolio piece about LLM evaluation.

   **Recommendation: (b).** It forces you to measure outcomes, which this project lacks. Its calibrated eval and pre-send gate are also the best showcase for (c).
2. **Gate mode — decided by implementation, change it if you disagree.** The pipeline now sends automatically when all hard checks pass and holds only the failing club. The alternative is approving every send yourself: a GitHub Environment with a required reviewer can pause the send job until you tap Approve.
3. **Send time.** Either commit to Monday around 07:30 KST *(recommended; confirm it in the interviews)*, or keep the afternoon slot and skip the external scheduler.

---

## Evidence log

### 2026-10-29 diagnosis

- **Live dashboard** (8804who.github.io/FootballNews, built 2026-10-29 06:13 UTC): 12 subscribers; pipeline 47/49; eval 64.9%.
- **`gh run list`:** `send_mail` succeeded on all 28 scheduled Mondays since 2026-04-20; Sep–Oct send jobs started between 06:58 and 08:34 UTC; `collect_news` failed on 2026-10-25 and 10-26.
- **GCS:** no `fotmob/` or `news_rss/` folder exists for 20261025 or 20261026; Arsenal and Man United repeat scoreboard rows between 20261019 and 20261026; the Chelsea 20261026 edition has no match section.
- **GCS eval reports** (`evaluation/` for 20260921–20261026): the leak was flagged next to false positives; 0 of 22 editions reached the 80% Korean ratio; alias false negatives on Oct 26.
- **`eval-history.json`:** 64.0–80.4% from 2026-08-03 to 2026-10-26.

### 2026-10-30 fixes

- **Leak extent:** the gate, run with the pre-fix `example.yml` (`git show 59c7ef0~1:example.yml`), finds the De Bruyne/Anderson/Guardiola example text in Chelsea (Aug 20, Sep 7, Oct 5, Oct 12), Man United (Aug 20), Spurs (Aug 24, Oct 12), Liverpool (Sep 14, Oct 5) and Arsenal (Oct 19), plus partial copies in 4 more editions. Spot-checked by grep.
- **Root cause:** regenerating Oct 12–18 with the one-string prompt but fictional examples copied the example into Chelsea and Man United (both held by the gate). With chat-format examples: 0 of 6.
- **Reversed result:** `datas/newsletter/20260831/newsletter_Chelsea.md` has "Chelsea vs Fulham 2-3"; FotMob has Fulham 2 – 3 Chelsea.
- **Public logs:** the latest `send_mail` run log (run 40285492149) contained subscriber addresses in plain text; 36 runs have logs. Counted without displaying any address.
- **Replay numbers:** 72 editions, Aug 17 – Oct 26: 35 held (28 repeats, 18 other-club or stale names, 7 missing, 1 reversed); score accuracy 89.6%; hallucination 17.7%; Korean median 99.6%.
