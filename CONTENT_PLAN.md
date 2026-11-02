<!-- /autoplan restore point: "/Users/kimjuseong/.gstack/projects/8804who-FootballNews/main-autoplan-restore-20261031-004855.md" -->
## Implementation plan
## Product Requirements Document: Natural Korean & richer content

**Author**: 8804 (drafted with Claude)
**Date**: 2026-10-31
**Status**: Approved 2026-10-31 (/autoplan: CEO, design, eng). Release split: collection first, content after a local preview. Blocks after the scoreboard.

---

### 1. Summary

Every edition is now accurate (harness: ~99% on metrics v2), but it still **reads like a machine wrote it**, and the news half is **thin**. This PRD covers two things. First, the Korean is rewritten so it sounds like a human sports editor writing 합쇼체 (you chose to keep 합쇼체). Second, three things readers want and our data already has get added: **league position, the next fixture in KST, and the injury list**. News items also get real substance from BBC's per-club feeds, which include a one-sentence summary of each story.

### 2. Contacts

| Role | Who |
| --- | --- |
| Owner / editor-in-chief | 8804 |
| Build, review, evaluation | Claude (this session) |
| Readers | 12 subscribers across 6 clubs (PRODUCT_PLAN.md §2) |

### 3. Background

Evidence from 120 sent editions (`datas/newsletter/*`) and the Oct 29 harness run (`evaluate/runs/`):

| Problem | Evidence | Root cause |
| --- | --- | --- |
| **Em dash everywhere**: the clearest sign of machine-written Korean | 406 uses in 97 of 120 editions | `prompt.yml` item format says "**headline** (보도) — one line"; `example.yml` repeats it |
| **Hedging filler** | "~할 수 있습니다" in 41 editions, "~로 보입니다" in 12, "~라는 신호" in 11 | The model has only a headline, so "why it matters" has to be a guess |
| **Generic fan-reaction filler** | "팬 입장에서는 / 팬들 사이" in 41 editions | The prompt asks for a "drama angle" even when the source has no drama |
| **Stock sports clichés** | "분위기를 잡/바꾸" in 27 editions, "꽂아/작렬/폭발" in 16, "변수" in 16, "빛났습니다" | The prompt encourages "vivid phrasing" without saying what vivid looks like |
| **Arrows and noun stacks** | "→" in 33 editions | Copied from the prompt's own style |
| **Confirmed news filed under 🧪 루머 밀** | Arteta's new contract, Gravenberch's red card, Kulusevski's return, a Spurs–Man Utd 1-1 result, all labelled 루머 | `prompt.yml:85` allows ✅ 공식 뉴스 only when FotMob has official transfers; `example.yml` puts a U19 goal under 루머 밀 |
| **Items with no news in them** | "Saka, 골 결정력이 더 위협적이 되었습니다", "Wirtz, 공격의 중심으로 다시 떠올랐습니다" | Opinion pieces and match reports pass the filter and get rewritten as news |
| **Vague headlines** | "벤치 한 방으로 분위기를 확 바꿨습니다" names no one | The "tease, not restate" rule (`prompt.yml:40`) has no floor |
| **Story verbs that contradict the score** | "Saka가 … 경기를 완전히 뒤집었습니다" while Arsenal led 1-0 | `match_facts` checks minute + player only |
| **Particle errors after English names** | "Newcastle와", "Isak와", "Palmer과", "Hoffenheim를" | No rule; the model guesses from the spelling |
| **Nothing about what's next** | 0 editions show the table, the next match or injuries | Not collected, although FotMob's team response (already captured each day) has `table`, `overview.nextMatch` and `squad[].injury.expectedReturn` |

Verified on 2026-10-31:
- FotMob team data includes the PL table (Arsenal 2nd, 21 pts, level with Man City), the next match (Liverpool vs Arsenal, 2026-11-01 16:30 UTC) and 5 injured players with expected returns ("Mid December 2026").
- `feeds.bbci.co.uk/sport/football/teams/{slug}/rss.xml` works for all 6 clubs, with 19–24 items each, and every item has a description and a publish date.

### 4. Objective

**Make Monday's email something a light fan would forward, not just skim.** It should read like a person wrote it and give the reader one more thing to talk about: where we stand, who's out, and when we play next.

Key results, measured with `evaluate/harness.py` on the 20260921 and 20261019 editions (12 per run), old prompt vs new:

| KR | Baseline | Target |
| --- | --- | --- |
| Em dashes per edition | 3.4 (sent editions) | **0** |
| AI-style signals per edition (`evaluate/style.py`) | measured at baseline | **−70% or better** |
| Blind pairwise "which reads more like a Korean human editor wrote it" (LLM judge, order randomized) | — | **new wins ≥ 9 of 12** |
| Overall harness score | 99.0% | **≥ 98%**, no regression |
| Score accuracy / match facts | 100% / 100% | **100% / 100%** |
| Non-rumor items under 🧪 루머 (manual read of 12 editions) | ~1 per edition | **0** |
| 순위 · 다음 경기 block in in-season editions (from the first live edition) | 0% | **100%** |

### 5. Market Segment(s)

From PRODUCT_PLAN.md §2. Design for P1; P2 and P3 should benefit without new sections built just for them.

- **P1 · 출근길 라이트팬** (most of the 12): missed the match, wants a three-minute rundown to talk about at work. Today they skim the headline and the scoreboard.
- **P2 · 새벽 직관러**: already knows the score and wants to know which rumors are real. Today confirmed news shows up labelled as rumor.
- **P3 · 입덕 중인 뉴비**: needs to know who's who. Today players appear with no position or context.

### 6. Value Proposition(s)

**P1: "Monday lunch, covered"**
- **Who:** office worker, 20s–30s, one club, rarely watches live.
- **Why:** wants to join Monday's conversation without watching at 3 a.m.
- **What before:** an accurate but machine-sounding recap; nothing on what's next.
- **How:** natural 합쇼체 copy, a headline that names someone, plus a code-rendered "📍 순위 & 다음 경기" block (position, gap, next kick-off in KST).
- **What after:** one line to repeat ("Arsenal 2위인데 City랑 승점 같아"), and the next kick-off already known.
- **Alternatives:** Naver Sports, YouTube highlights, group chats.

**P2: "Rumors I can trust"**
- **Who:** watches live, lives in communities.
- **Why:** rumor noise and mistranslation.
- **What before:** confirmed news filed as 루머, one-line items written from a headline alone.
- **How:** ✅ 확정 소식 kept separate from 🧪 루머; BBC summaries give each item a concrete fact; opinion pieces and repeated match reports are dropped.
- **What after:** a short, sorted list where each item says what actually happened.
- **Alternatives:** 에펨코리아, X, FotMob.

**P3: "Who's who"**
- **Who:** a new fan.
- **Why:** doesn't know the squad.
- **What before:** names without positions; injuries scattered through gossip items.
- **How:** a "🏥 부상자 명단" table with position (in Korean) and expected return.
- **What after:** knows who's missing and roughly when they return.
- **Alternatives:** YouTube explainers, friends.

### 7. Solution

#### 7.1 Language: natural 합쇼체 (prompt + examples; no code risk)

1. **Rewrite the Tone & Voice rules in `prompt.yml`** around a short list of banned habits, each with a before → after pair:
   - No em dashes (—) or arrows (→) anywhere.
   - No hedging: no "~할 수 있습니다", "~로 보입니다" or "~라는 신호입니다", unless the source itself says "could".
   - No generic fan-reaction lines ("팬 입장에서는…", "팬들 사이에서 화제…") unless the source reports a reaction.
   - No stock clichés: 분위기를 잡다/바꾸다, 작렬, 폭발, 존재감, 서사, 변수, 빛났다, 스포트라이트, 모양새, 눈에 띈다.
   - No translationese: "~에 따르면" opening, "~로 알려진", "이는", "또한" sentence starts, passive "보도되었습니다/제기됐습니다".
   - Vary sentence length; join clauses with "~했고 / ~했는데 / ~했지만" instead of stacking short "~했습니다." sentences.
   - Concrete beats vivid: a minute, a name, a number.
2. **Particle rule:** choose 이/가, 을/를, 은/는, 와/과 and (으)로 by how the English name is said in Korean (Newcastle과, Isak과, Palmer와, Bayern München과).
3. **Headline rule:** keep the tease, but it must name a player or the opponent.
4. **Item format:** `- **한 줄 제목** (보도)` on one line, then one or two plain sentences, then the source tag. No dash separator.
5. **Rewrite `example.yml`** in that voice (names stay fictional, which `gate.py` already checks), and move the misfiled U19 example out of 루머.

#### 7.2 News that says something (data + prompt)

1. **BBC per-club RSS** (`scrappers/news_rss.py`, slugs in `teams.yml`):
   - Collected daily next to Google News.
   - Kept only when the title or summary names the club.
   - The summary is stored as a `  > …` line under the headline.
   - `edition.NewsItem` gets a `summary` field, and the model sees `요약: …` under each line.
   - Links go straight to bbc.co.uk.
2. **News section restructure:**
   - `### ✅ 확정 소식`: anything reported as done (official transfers, contracts, injuries, bans, returns).
   - `### 🧪 루머`: "linked with / target / bid / gossip" stories only.
   - `### 🎭 드라마 앵글`: only when the source reports a real human story.
   - Every item must report an event. Analysis and opinion pieces are skipped. Two or three good items beat five weak ones.
3. **Drop repeated match reports** (`edition.load_news`): a headline with a scoreline about a match that's already in this week's scoreboard is dropped, like the existing stale-preview filter.

#### 7.3 New blocks, rendered by code (no LLM, so nothing can be invented)

1. **`## 📍 순위 & 다음 경기`**:
   - One line on position and gap, for example "**2위** · 8경기 21점. 선두 Man City와 승점은 같고 골득실에서 밀립니다."
   - A three-row mini table (the team above, this club, the team below).
   - The next one or two fixtures in KST, for example "11월 2일 (월) 오전 1:30 · Liverpool 원정 · Premier League".
2. **`## 🏥 부상자 명단`**:
   - A table of 선수 | 포지션 | 복귀 예상 from FotMob's squad injuries.
   - "Mid December 2026" becomes "12월 중순"; "Doubtful" becomes "출전 불투명".
   - Omitted when nobody is injured.
3. **Data:**
   - `collect_news.py` saves `team_daily_report_{team}_overview.json` (the league table rows plus injuries) next to the fixture list.
   - `edition.py` reads the newest copy, as it already does for fixtures.
4. **Placement:** after the scoreboard and before 이적 & 뉴스. Readers who only skim still get "where we stand / what's next". Markdown only, so it uses the existing `EMAIL_STYLES` (h2 label, table) and DESIGN.md needs no new tokens.
5. **Evaluation:**
   - The metrics, judge and gate skip these two blocks: they're copied from the source by code, so scoring them would only measure the template.
   - Unit tests cover the template instead.
   - Old editions don't have these blocks or the news summaries, so their scores don't change and **`METRICS_VERSION` stays 2**.

#### 7.4 Measurement

- **`evaluate/style.py`:** counts AI-style signals per edition (the patterns in §3). Shown in the harness report as information only. It's not weighted and not a gate check: style isn't a defect.
- **A blind pairwise judge**, run once for this PRD, compares old and new editions on the same inputs.
- **`gate.py` warning (report-only):** "역전/뒤집" used when the club never trailed, checked against the goal order in the match events.

#### Assumptions and open questions

- *Assumption:* BBC's team feed keeps its current URL and format. If it fails, collection falls back to Google News only, and a fetch error never stops collection.
- *Assumption:* FotMob's injury list is current enough on Monday morning. It shows "expected return", not certainty, and the copy says 예상.
- *Open:* should the headline become the email subject? It needs headlines that are reliably good first. **Deferred until two live editions show the new headline rule holds.**
- *Open:* switching to gpt-5.4-mini with low reasoning effort (harness: +0.6, cheaper and faster) is a separate decision. This PRD keeps the model fixed so the comparison isolates the prompt.

### 8. Release

**Phase 1: this session, local, not committed until you review:**
- Language (7.1), news (7.2), the new blocks (7.3) and measurement (7.4).
- Unit tests; a harness comparison of old vs new prompt; a live demo edition built from fresh data.

**Goes live** once you commit and push before Monday's collect (Nov 2, cron 00:30 UTC; it actually starts around 05:30 UTC):
- The overview data and BBC items only exist in folders collected after the push.
- So the Nov 2 edition gets the new language and the 순위/다음 경기 block (from Monday's collection), plus BBC items from Monday's run only.
- The Nov 9 edition is the first full week.

**Not in v1:**
- Switching to 해요체 (you chose 합쇼체).
- Korean spellings of names (proper nouns stay English, and the name checks depend on it).
- The headline as email subject.
- 👍/👎 feedback links, send-time changes, more clubs, model switch, `EMAIL_STYLES` changes.

---

### 9. Reviews

_Filled in by the plan reviews (director/CEO, design, engineering) below._

<!-- autoplan-accepted:ceo -->
- Copy and KRs make no 출근길 / lunch / 오늘 / 어제 promises; the prompt forbids time words relative to the read time.
- The footer gains a one-line reply prompt and 👍/👎 mailto links with a prefilled subject per club and edition; tested in test_send_mail.
- Next fixtures come from fixtures.json, not cancelled, kickoff ≥ edition end, any competition, labelled; unit-tested.
- Standings render only when this club's table `played` equals its finished fixtures in that league before the edition end; otherwise omitted; unit-tested.
- Injured players named in this week's match events are dropped from the injury list; unit-tested.
- ✅ 확정 only for the closed list with a 보도 source, default 루머; gate.py adds a report-only warning when a 확정 item cites a 가십 line or a linked/target/bid/talks headline; unit-tested.
- BBC items are deduped against Google News by normalised title, keeping the BBC item with its summary; unit-tested.
- prompt.yml and example.yml contain no em dashes or arrows; llm.py post-processes any em dash out of model output; unit-tested.
- A deterministic particle fixer handles club names (batchim lookup); unit-tested.
- style.py reports banned signals and a separate held-out set; the harness report shows both.
- A blind pairwise judge on two axes (natural, fun/forwardable) runs on the harness editions; a blind A/B file is written for the owner's read.
- A 2×2 harness run (old/new prompt × gpt-5-mini / gpt-5.4-mini low) is reported.
<!-- /autoplan-accepted:ceo -->

<!-- autoplan-accepted:design -->
- 📍 block: `## 📍 순위 & 다음 경기`, then `**{N}위 · {P}경기 승점 {pts}**` alone, then a gap sentence paragraph, then a 3-row table 순위|팀|경기|승점|득실 with the own row bold, then `**다음 경기**` and up to 2 bullets `{M}월 {D}일({요일}) {새벽/오전/낮/오후/밤} {h}:{mm} · {opponent} {홈/원정} · {competition}`; a rendered-HTML test asserts the hero line is the only strong in the first paragraph.
- 🏥 block: `## 🏥 결장 예상`, bullets `{name} · {Korean position} · {return}` sorted soonest first, max 6 + `외 N명`; omitted when empty.
- News items: the title line ends with two spaces (a hard break) before the body; tested on rendered HTML.
- The quiet-week fallback is rewritten in 합쇼체, and the code blocks still render in quiet and news-only weeks (first in news-only weeks).
- The news call receives the injury list and next fixtures as read-only context; the evaluation and gate count those names as source names.
- The headline is capped at about 28 Hangul characters and names a player or opponent.
- DESIGN.md gains a Decisions Log row for the new blocks.
<!-- /autoplan-accepted:design -->

<!-- autoplan-accepted:eng -->
- generate writes inputs/{team}.json beside each newsletter (news items with tag, title, outlet, kind, link, summary; context names; block render reasons; dash replacement count); evaluate_newsletter, gate.check_edition and judge use it when present and the legacy path otherwise.
- Before/after evaluation scores over every local past edition are identical (diff = 0) and tests/golden passes.
- NewsItem has summary; every source pool uses headline + summary; a test shows a summary-only fact is grounded.
- The overview extraction and the BBC fetch never raise out of collect_news; BBC uses requests with a 15s timeout, writes team_daily_report_{team}_bbc.json, caps at 6, filters live/video/audio URLs, matches the club in the title or the summary's first sentence, and logs a warning on 0 items; tested with an HTTP error, malformed XML and missing keys.
- Replaces the ceo obligation "Injured players named in this week's match events are dropped": nobody is dropped; standings and injuries render only from an overview snapshot with collected_at ≥ edition end; unit-tested.
- The match-report filter (generation only) requires the actual final score, the opponent name and publish ≥ kickoff; tests cover "out for 2-3 weeks" and "4-3-3" staying.
- Blocks: the heading follows content; time formatting is fixed UTC+9 with a Korean weekday list; tests cover Sat 15:00 UTC → (일) 0시, 1st/20th place, ties, 0 played, a finished or cancelled next fixture.
- The news-section headings live in one module; gate's unlinked check covers 확정 items except "(FotMob 공식)".
- When the LLM returns no sections, 🌙 renders with the code blocks.
- generate_dashboard finds the scoreboard by heading.
- The particle fixer handles ㄹ+로 and compound particles and leaves unknown clubs alone; tested.
- The dash post-processor never touches score hyphens; tested.
- The harness adds 20261026 as a held-out week; the pairwise judge runs both orders.
<!-- /autoplan-accepted:eng -->
## Review record

Run: /autoplan 2026-10-31 · base `main` · outside voice: Codex not installed, so each phase used an independent Claude reviewer agent (`[subagent-only]`; consensus cells are N/A by rule). UI scope: yes (new rendered email blocks; the keyword scan found 0 terms, so this was a judgment call). DX scope: no.

### Phase 1 · CEO / director review

**Premises**
| # | Premise | Verdict |
| --- | --- | --- |
| P1 | "Every edition is accurate (~99%)" | Holds only for harness replays: the judge is gpt-5-mini scoring gpt-5-mini, and no live edition has been sent on the new pipeline. Accepted as "accurate on replays", not "proven live". |
| P2 | "Readers want table / next match / injuries" | A hypothesis (PRODUCT_PLAN §7), not a fact. Accepted, with a feedback line added so it can be measured. |
| P3 | "Monday lunch" value prop | **Wrong today**: sends land around 15:00–17:30 KST. The copy and KRs must not promise 출근길 or lunch until send time is fixed. Send time is still your open decision. |
| P4 | "Code-rendered means it can't be wrong" | **Wrong**: a stale overview copy (a failed Monday collection) or `nextMatch` can show a match that's already been played as "next". Guards added. |
| P5 | "The LLM can decide 확정 vs 루머" | The two errors aren't equally bad: a rumor filed as 확정 is the De Bruyne failure again. A closed rule plus "when unsure, it's 루머" was added. |

**What already exists:** `edition.load_fixtures` (newest fixture list), `edition._is_stale_preview` (the pattern for the match-report filter), `citations.py` (tags → links), `gate.py` (report-only warnings), `harness.py` + `runs.yml` (prompt/model variants), `team_names.aliases` (club spellings), `example_names()` (fictional-name guard).

**Dream state:** CURRENT (accurate, machine-sounding, afternoon, unmeasured) → THIS PLAN (natural, richer, self-consistent, first reader signal) → 12-MONTH (arrives before work, measured by replies and opens, the voice as the brand).

**Findings → decisions**
| Finding | Severity | Decision |
| --- | --- | --- |
| Value prop contradicted by send time | critical | Copy and KRs say nothing about 오늘, 어제, 출근길 or lunch. Send time goes to the gate as a reminder (your decision). |
| Building blind | high | Add a one-line reply prompt and 👍/👎 mailto links to the footer (no new infrastructure). `signup_url` stays empty until you supply the form link. |
| Release stacking on Nov 2 | high | **Taste decision → gate** (ship all for Nov 2, or collection first and content on Nov 9). Code is split so either works. |
| Stale or contradictory code blocks | high | Next fixtures from `fixtures.json` with kickoff ≥ edition end. Standings only if the table's `played` equals finished league fixtures before the edition end. Injured players who appear in this week's match events are dropped. |
| ✅ 확정 asymmetry | high | Closed list (contract, club-confirmed injury, ban, return, result), cited line must be 보도, default to 루머. Report-only gate warning when a 확정 item cites 가십 or a linked/target/bid/talks headline. |
| KRs can't see the BBC fix | medium | 7.2 is measured on a live demo edition built from fresh data, not on the old weeks. |
| BBC duplicates via Google News | medium | Dedupe by normalised title; keep the direct BBC item. |
| Voice flattening / Goodhart | medium | Judge on two axes (natural, fun/forwardable); keep the praised headline as a positive example; style.py also tracks held-out signals the prompt never names; your own blind read is the deciding KR. |
| Em dashes in prompt.yml (25) and example.yml (4) | medium | Remove them all; also a deterministic em-dash post-processor. |
| Particles | medium | Deterministic fixer for club names (batchim lookup); prompt rule for player names. |
| Model held fixed | medium | Run a 2×2 harness (old/new prompt × gpt-5-mini / gpt-5.4-mini low), under $1. |

**Error & Rescue Registry**
| Failure | Rescue |
| --- | --- |
| BBC fetch fails | Log it, continue with Google News; never fail collection |
| overview.json missing | Both blocks omitted, no heading |
| Table stale (played count mismatch) | Standings omitted, fixtures still shown |
| Unknown FotMob return string | Shown as 미정, logged |
| No upcoming fixture (season over) | 다음 경기 line omitted |

**Failure Modes Registry**
| Mode | Detection |
| --- | --- |
| A played match shown as next | Unit test: fixture kickoff < edition end is never shown |
| Pre-match table next to the result | Unit test: played-count guard |
| Rumor filed as 확정 | Gate warning (report-only) + manual read KR |
| New AI-style tics replace the old ones | Held-out signals in style.py |
| A soft break merges title and body | Unit test on the rendered HTML |

**NOT in scope (CEO):** send-time move (your decision), headline as subject, preheader, ESP / open tracking, model switch (data only from the 2×2).

<!-- autoplan-accepted:ceo -->
- Copy and KRs make no 출근길 / lunch / 오늘 / 어제 promises; the prompt forbids time words relative to the read time.
- The footer gains a one-line reply prompt and 👍/👎 mailto links with a prefilled subject per club and edition; tested in test_send_mail.
- Next fixtures come from fixtures.json, not cancelled, kickoff ≥ edition end, any competition, labelled; unit-tested.
- Standings render only when this club's table `played` equals its finished fixtures in that league before the edition end; otherwise omitted; unit-tested.
- Injured players named in this week's match events are dropped from the injury list; unit-tested.
- ✅ 확정 only for the closed list with a 보도 source, default 루머; gate.py adds a report-only warning when a 확정 item cites a 가십 line or a linked/target/bid/talks headline; unit-tested.
- BBC items are deduped against Google News by normalised title, keeping the BBC item with its summary; unit-tested.
- prompt.yml and example.yml contain no em dashes or arrows; llm.py post-processes any em dash out of model output; unit-tested.
- A deterministic particle fixer handles club names (batchim lookup); unit-tested.
- style.py reports banned signals and a separate held-out set; the harness report shows both.
- A blind pairwise judge on two axes (natural, fun/forwardable) runs on the harness editions; a blind A/B file is written for the owner's read.
- A 2×2 harness run (old/new prompt × gpt-5-mini / gpt-5.4-mini low) is reported.
<!-- /autoplan-accepted:ceo -->

Phase 1 complete. Claude subagent: completed, 11 findings. Codex: unavailable (not installed). Consensus: N/A (outside unavailable).

### Phase 2 · Design director review

**Scores:** hierarchy 6/10 · missing states 3/10 · journey 6/10 · specificity 7/10 (language), 4/10 (blocks) · ambiguity risk high in §7.3. After the decisions below: missing states and block specificity are both written out as rules, giving an estimated 8/10.

**Findings → decisions**
| Finding | Severity | Decision |
| --- | --- | --- |
| C1 `.wrap h2 + p strong` turns "**2위**" into a 20px headline and breaks the line | critical | The hero line is a single bold paragraph `**2위 · 8경기 승점 21**`; the gap sentence follows as its own paragraph. A rendered-HTML unit test covers it. |
| C2 A soft break merges the news title and body once the em dash is gone | critical | A post-processor adds a hard break (two trailing spaces, invisible in plain text) after the `(보도)/(가십)` tag line; tested on rendered HTML. |
| H1 Stale next match / wrong-week table | high | Same guards as CEO (cross-phase theme). |
| H2 Gap and table rules | high | The gap is to the team directly above (the leader shows its lead over 2nd). Ties: "승점은 같고 골득실에서 앞섭니다/밀립니다". 1st/20th clamp to rows 1–3 / 18–20. 0 played → omitted. Columns 순위 \| 팀 \| 경기 \| 승점 \| 득실. Own row bold. FotMob short names. "8경기 승점 21". |
| H3 Code copy needs particles and Korean time style | high | Fixture lines carry no particles after names ("Slavia Prague 원정"). Times: 0–5시 새벽, 6–11 오전, 12 낮, 13–17 오후, 18–23 밤; 00:00 → 자정; "11월 5일(목)" with no space. |
| H4 Missing states | high | News-only week: blocks first. Quiet week: blocks still render with 🌙. The fallback's 해요체 is rewritten in 합쇼체. Missing data: block omitted. Season over: no next line. 0 played: no table. |
| H5 Injuries contradict the news | high | The news call gets the injury list and next fixtures as read-only context ("don't restate return dates"); their names join the evaluation's source pool. The return map covers Early/Mid/Late + month, the current year dropped, Unknown/past → 미정, sorted soonest first, capped at 6 + "외 N명". Unknown strings → 미정 + log. Positions use a detailed Korean map with a role fallback. |
| M1 Three tables in a row | medium | Next fixtures and injuries are bullet lists, not tables; injuries sit right under next fixtures. **Taste → gate:** block placement (after the scoreboard, or at the end). |
| M2 Inbox first impression / preheader | medium | Deferred to TODOS (send path; pairs with headline-as-subject). |
| M3 Headline length | medium | Prompt cap: about 28 Hangul characters. |
| M4 ✅ vs 🧪 rules | medium | (가십) never under ✅; previews dropped; press quotes go to 드라마 앵글 only if notable; FotMob items labelled "(FotMob 공식)". |
| M5 DESIGN.md | medium | Add a Decisions Log row; update the "Data/Tables" line. |
| M6 P3 positions on first mention | medium | Deferred: it adds prompt load against the naturalness goal. Positions appear in the injury list. |
| M7 Read-time words | medium | Same as CEO: no 오늘/어제. |
| M8 BBC duplicates | medium | Same as CEO. |

**Design litmus:** the first screen shows masthead → headline → match story → scoreboard → 📍 hero line. Every new block has a defined empty state, there are no new tokens, and Markdown only.

<!-- autoplan-accepted:design -->
- 📍 block: `## 📍 순위 & 다음 경기`, then `**{N}위 · {P}경기 승점 {pts}**` alone, then a gap sentence paragraph, then a 3-row table 순위|팀|경기|승점|득실 with the own row bold, then `**다음 경기**` and up to 2 bullets `{M}월 {D}일({요일}) {새벽/오전/낮/오후/밤} {h}:{mm} · {opponent} {홈/원정} · {competition}`; a rendered-HTML test asserts the hero line is the only strong in the first paragraph.
- 🏥 block: `## 🏥 결장 예상`, bullets `{name} · {Korean position} · {return}` sorted soonest first, max 6 + `외 N명`; omitted when empty.
- News items: the title line ends with two spaces (a hard break) before the body; tested on rendered HTML.
- The quiet-week fallback is rewritten in 합쇼체, and the code blocks still render in quiet and news-only weeks (first in news-only weeks).
- The news call receives the injury list and next fixtures as read-only context; the evaluation and gate count those names as source names.
- The headline is capped at about 28 Hangul characters and names a player or opponent.
- DESIGN.md gains a Decisions Log row for the new blocks.
<!-- /autoplan-accepted:design -->

Phase 2 complete. Claude subagent: completed, 2 critical, 5 high, 8 medium. Codex: unavailable. Consensus: N/A.

### Cross-phase themes
- **Staleness / self-contradiction of the code blocks**: flagged by CEO (P4) and design (H1). High confidence.
- **Confirmed-vs-rumor rules**: CEO (asymmetry) and design (M4).
- **BBC duplicates**: CEO and design (M8).
- **Particles must be handled in code, not left to the model**: CEO and design (H3).
- **No "lunch"/"오늘" promises**: CEO (critical) and design (M7).

### Phase 3 · Engineering review

**Architecture (after this plan)**
```
collect_news.py (daily)
 ├─ fotmob._get_team_data ──┬─ matches.md / transfers.md / fixtures.json (+ tournament_id)
 │                          └─ overview.json  {collected_at, league, table rows, injuries}   [try/except, never fails collect]
 ├─ news_rss (Google, 5)  ──── news_rss/{d}/team_daily_report_{team}.md        (unchanged format)
 └─ news_rss.bbc (≤6, 15s timeout) ── news_rss/{d}/team_daily_report_{team}_bbc.json {title, link, published, summary}
                                       (separate file: old generate code never reads it)

generate_newsletter.py (weekly)
 edition.build_inputs(team, run_date)
   ├─ matches (by kickoff) ──────────────► LLM matches_report
   ├─ news = Google ∪ BBC (BBC wins dupes; Google-BBC dropped on BBC days;
   │         match reports of played matches dropped) ─► LLM news (tags + 요약 + "shown separately" names)
   └─ blocks.render(overview, fixtures, matches) ──► 📍 순위 & 다음 경기 · 🏥 결장 예상 (code, no LLM)
 tidy.py (dashes → commas, hard break after tag line, club particles) on LLM output
 → newsletter_{team}.md  +  inputs/{team}.json (exactly what the model saw + block render reasons)

evaluate / gate / judge
 read inputs/{team}.json when present (new editions), else edition.load_news legacy path (old editions unchanged)
 strip code blocks before scoring; source pool = headline + summary + context names
```

**Findings → decisions**
| Finding | Severity | Decision |
| --- | --- | --- |
| H1 The evaluation re-derives inputs, so new filters change old scores | high | **Accepted.** Save `inputs/{team}.json` at generation; evaluate, gate and judge read it, with the legacy fallback unchanged. The new filters run only in the generation path. Prove it with a before/after score diff over all local editions (must be 0) and the golden tests. |
| H2 BBC summaries never reach the evaluation | high | **Accepted.** `NewsItem.summary`; the source pools use headline + summary; a test covers an item supported only by its summary. |
| H3 Monday's collection becomes fragile | high | **Accepted.** Overview extraction and the BBC fetch go in try/except (log, write nothing); BBC is fetched with `requests` timeout 15s; the table is picked by league name; a warning is logged when BBC returns 0 items. Existing FotMob failure semantics are unchanged (they still alert). |
| H4 One push into Monday's send | high | **Cross-phase with CEO → gate.** BBC goes in a separate file so old generate code is unaffected; collection and generation changes can be pushed separately. |
| M1 The injury drop removes the wrong players | medium | **Replaces the CEO obligation "drop injured players named in this week's events".** Nobody is dropped; injuries and standings render only from an overview snapshot collected at or after the edition end (L6). |
| M2 Dedupe won't hold | medium | Explicit merge preferring the summary; Google items with a BBC outlet are dropped on days a BBC file exists; /live/, /videos/, /sounds/ and podcast URLs are filtered; BBC capped at 6 per run. |
| M3 Summary line parsing state | medium | Avoided: BBC is stored as JSON, so no `  >` lines and no state machine. |
| M4 The match-report filter catches real news | medium | It requires the match's actual final score (either order), the opponent's name and a publish time ≥ kickoff. |
| M5 Standings edge cases | medium | Tiebreak wording from FotMob order (points, GD, GF); window clamps at 1st/20th; omitted at 0 played; heading follows content (📍 현재 순위 / 📅 다음 경기 / both); fixtures.json gains `tournament_id` with a name fallback; render or omit reasons go in inputs.json; KR = "rendered whenever data is fresh". |
| M6 Next fixtures / KST | medium | Not finished, not cancelled, kickoff ≥ edition end; fixed UTC+9 offset; a Korean weekday list; times as "새벽 5시", "오전 9시", "낮 12시", "오후 3시", "저녁 8시", "밤 11시 30분", and midnight as "0시"; a test for Sat 15:00 UTC → "(일) 0시". |
| M7 The plan's example breaks its own rule | medium | Fixed in the final spec; that fixture becomes a test case. |
| M8 Context brings the LLM back in | medium | Only names are passed ("shown separately: …") with "never write an item from this list". |
| M9 Heading rename spans files | medium | One constant set in `newsletter_sections.py`; `_unlinked_items` also checks 확정 items, exempting "(FotMob 공식)". |
| M10 Empty news section | medium | `has_news` is counted from the inputs actually sent; when the LLM returns nothing, 🌙 renders together with the code blocks. |
| M11 Fragile trailing-space break | medium | Added in code (tidy.py), and a blank line between title and body is removed; tested on rendered HTML. |
| M12 Dashboard score line | medium | `generate_dashboard` finds the scoreboard table by its heading, not by `table_rows[2]`. |
| M13 Particle fixer details | medium | ㄹ+로; rewrite only when followed by non-Hangul; unknown clubs left alone; templates use the same helper; prompt examples use fictional clubs. |
| L1 Dash post-processor | low | " — ", "–", "―" become ", "; " → " becomes ", "; hyphens in scores are untouched; replacements counted in inputs.json, and the KR uses the raw count. |
| L2 The rule text contains a dash | low | The prompt writes "U+2014 (긴 줄표)" in words. |
| L3 Judge rigor | low | Both orders, consistent wins only; 20261026 added as a held-out week. |
| L4 Escaping | low | FotMob strings are escaped for `\|*_<`; no links in the blocks. |
| L5 Mapping | low | As in the design H5 decision. |
| L6 Freshness | low | Accepted (see M1). |
| L7 Headline length | low | Measured in style.py, not truncated. |
| L8 DESIGN.md numeric table | low | Recorded in the Decisions Log row. |
| L9 PRD contradictions | low | The final spec below supersedes §7–8. |
| L10 BBC club match | low | Title, or the summary's first sentence. |

**Test plan:** `~/.gstack/projects/8804who-FootballNews/main-content-test-plan-20261031.md`.

**NOT in scope (eng):** per-team isolation of the existing FotMob failure path (it changes alert semantics), a backfill re-upload to GCS, TZ database support.

<!-- autoplan-accepted:eng -->
- generate writes inputs/{team}.json beside each newsletter (news items with tag, title, outlet, kind, link, summary; context names; block render reasons; dash replacement count); evaluate_newsletter, gate.check_edition and judge use it when present and the legacy path otherwise.
- Before/after evaluation scores over every local past edition are identical (diff = 0) and tests/golden passes.
- NewsItem has summary; every source pool uses headline + summary; a test shows a summary-only fact is grounded.
- The overview extraction and the BBC fetch never raise out of collect_news; BBC uses requests with a 15s timeout, writes team_daily_report_{team}_bbc.json, caps at 6, filters live/video/audio URLs, matches the club in the title or the summary's first sentence, and logs a warning on 0 items; tested with an HTTP error, malformed XML and missing keys.
- Replaces the ceo obligation "Injured players named in this week's match events are dropped": nobody is dropped; standings and injuries render only from an overview snapshot with collected_at ≥ edition end; unit-tested.
- The match-report filter (generation only) requires the actual final score, the opponent name and publish ≥ kickoff; tests cover "out for 2-3 weeks" and "4-3-3" staying.
- Blocks: the heading follows content; time formatting is fixed UTC+9 with a Korean weekday list; tests cover Sat 15:00 UTC → (일) 0시, 1st/20th place, ties, 0 played, a finished or cancelled next fixture.
- The news-section headings live in one module; gate's unlinked check covers 확정 items except "(FotMob 공식)".
- When the LLM returns no sections, 🌙 renders with the code blocks.
- generate_dashboard finds the scoreboard by heading.
- The particle fixer handles ㄹ+로 and compound particles and leaves unknown clubs alone; tested.
- The dash post-processor never touches score hyphens; tested.
- The harness adds 20261026 as a held-out week; the pairwise judge runs both orders.
<!-- /autoplan-accepted:eng -->

Phase 3 complete. Claude subagent: completed, 4 high, 13 medium, 10 low. Codex: unavailable. Consensus: N/A.

### Final spec (supersedes §7–8 where they differ)
- **Language:** §7.1, plus no em dashes or arrows in prompt.yml or example.yml (written in words), fictional names in every example, a headline of about 28 characters that names someone, no read-time words (오늘, 어제, 출근길).
- **News:** sections `### ✅ 확정 소식` (closed list, 보도 only, FotMob items "(FotMob 공식)"), `### 🧪 루머`, `### 🎭 드라마 앵글`. BBC summaries go in as `요약:`. Each title line is followed by a hard break, then the body.
- **Blocks:** `## 📍 순위 & 다음 경기` (or `## 📍 현재 순위` / `## 📅 다음 경기`), then `**2위 · 8경기 승점 21**`, then the gap sentence, then the 3-row table, then `**다음 경기**` with bullets such as "11월 5일(목) 새벽 5시 · Slavia Prague 원정 · Champions League". Then `## 🏥 결장 예상` with bullets such as "Bukayo Saka · 오른쪽 윙어 · 12월 중순 복귀 예상". These come after the scoreboard (or first in a news-only week), before 이적 & 뉴스.
- **Footer:** a reply line plus 👍 / 👎 mailto links.
- **Release:** your choice at the gate.

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
| 1 | 0 | Run design phase despite 0 keyword hits | Mechanical | P1 | The plan adds rendered email blocks | Skip design |
| 2 | 1 | Drop lunch/출근길 promises | Mechanical | P5 | Contradicted by send time | Keep wording |
| 3 | 1 | Reply + 👍/👎 mailto footer | Mechanical | P2 | In blast radius, no infra, first reader signal | Defer feedback |
| 4 | 1 | Split release Nov 2 vs Nov 9 | Taste | P6 | Your release call; code works either way | — |
| 5 | 1 | Staleness guards for blocks | Mechanical | P1 | Prevents self-contradiction | Trust newest copy |
| 6 | 1 | Closed 확정 rule + gate warning | Mechanical | P1 | Asymmetric error cost | LLM free choice |
| 7 | 1 | BBC dedupe | Mechanical | P4 | Duplicate items | — |
| 8 | 1 | Two-axis judge + held-out signals + owner blind file | Mechanical | P1 | Avoid Goodhart and flattening | One-axis judge |
| 9 | 1 | Strip em dashes from prompt/examples + post-processor | Mechanical | P5 | Prompt teaches by example | Prompt rule only |
| 10 | 1 | Club-name particle fixer | Mechanical | P5 | Deterministic beats asking | Prompt only |
| 11 | 1 | 2×2 prompt × model harness | Mechanical | P1 | <$1, attributes the gain | Model fixed, untested |
| 12 | 2 | Hero line as a single bold paragraph | Mechanical | P5 | Works with the existing CSS rule | CSS change |
| 13 | 2 | Hard break after the news tag line | Mechanical | P5 | CommonMark soft break | Rely on the model |
| 14 | 2 | Gap to the team directly above | Mechanical | P5 | Useful for mid-table clubs | Gap to the leader |
| 15 | 2 | Bullets for fixtures and injuries | Mechanical | P5 | Avoid three tables in a row | Tables |
| 16 | 2 | Block placement after the scoreboard | Taste | P1 | Skimmers see it; CEO preferred news higher | At the end |
| 17 | 2 | Preheader deferred | Mechanical | P3 | Send path; pairs with subject change | Build now |
| 18 | 2 | P3 positions on first mention deferred | Mechanical | P3 | Prompt load vs naturalness | Build now |
| 19 | 3 | Save model inputs per edition | Mechanical | P5 | Keeps old scores stable | Re-derive in evaluate |
| 20 | 3 | BBC as a separate JSON file | Mechanical | P5 | No parser state; old code unaffected | Same md file |
| 21 | 3 | Freshness guard instead of dropping injured players | Mechanical | P1 | Subbed-off injured players matter | Drop by events |
| 22 | 3 | Names-only context for the news call | Mechanical | P5 | Keeps the LLM out of the blocks | Full context / none |
| 23 | 3 | Held-out week 20261026 | Mechanical | P1 | Avoid overfitting | Two weeks only |

## Build results (2026-10-31)

Measured with `evaluate/harness.py` on 18 editions (20260921, 20261019, plus 20261026 held out while tuning), all re-scored by the same evaluation with the judge. "before" is the committed pipeline (HEAD 4608e25) run from a `git archive` copy, so it includes the prompt bug below.

| | before (gpt-5-mini) | after (gpt-5-mini) | before (gpt-5.4-mini low) | after (gpt-5.4-mini low) |
| --- | --- | --- | --- | --- |
| Overall | 98.4% | **99.1%** | 97.8% | 98.9% |
| Match facts | 91.7% | 97.9% | 77.8% | 100.0% |
| Faithfulness (judge) | 96.7% | 96.9% | 97.2% | 94.0% |
| Korean ratio | 98.0% | 99.0% | 99.2% | 98.5% |
| Prompt-banned AI habits per edition (model's own output) | 6.1 | **1.2** | 5.1 | 0.2 |
| Long dashes per edition (model's own output) | 3.8 | **0.0** | 3.1 | 0.0 |
| Held-out AI habits per edition | 0.7 | 0.2 | 0.7 | 0.2 |
| 3 identical endings in a row | 2.4 | 4.1 (worse) | 2.9 | 4.3 |
| Headline length | 35 chars | 26 chars | 34 | 31 |
| Cost per edition | $0.0117 | $0.0148 | $0.0061 | $0.0061 |

Held-out week alone (20261026): banned habits 5.0 → 1.8, long dashes 2.7 → 0.

**Blind pairwise judge** (gpt-5-mini, both orders, a win counts only when both orders agree), before vs after over the 18 pairs:

| Prompt round | natural (before / after / split) | fun (before / after / split) |
| --- | --- | --- |
| 1: strict, "a little dry" | 7 / 4 / 7 | 15 / 0 / 3 |
| 2: lively voice, angle per section, new examples | 5 / 6 / 7 | 11 / 3 / 4 |
| 3 (shipped): + no jargon, no English quotes, no outlet names | 6 / 6 / 6 | 10 / 3 / 5 |
| 3, held-out week only | 1 / 2 / 3 | 2 / 2 / 2 |

The judge calls the new copy cleaner and more idiomatic, and the old copy livelier. Its reasons credit the old copy's volume of gossip and speculative "drama" lines, the very hedges this plan removes, and it is the same model as the writer. **Your own blind read decides**: `evaluate/runs/blind/` (18 pairs, key in `key.json`).

**Found while building**
- The system prompt (`prompt.yml` system rules: tone, 합쇼체, banned clichés) had been reaching the model **one character per line** since it was written: `generate_prompt` looped over a text entry like a list. Fixed, with a test.
- Penalty shootouts weren't in the match data: Arsenal's Carabao Cup exit to Fleetwood (1-1, 3-5 on penalties) would have gone out as "1-1로 비겼습니다". FotMob's fixture list now carries it into the Result line.
- FotMob return strings beyond the plan ("Back in training", "About a week") are mapped; unknown ones show 미정 and are logged.
- The 역전 gate check was first too noisy on old editions (metaphors). It is now limited to the match sections and to completed-action forms; on 120 past editions it adds 6 warnings, all real errors.

**Invariance:** all 120 local past editions score identically before and after (0 metric changes, 0 changed existing checks). `METRICS_VERSION` stays 2. Tests: 79 → 125, all passing.

**Live preview** of the Nov 2 edition from today's data: `evaluate/runs/live-demo/20261102/` (blocks computed as of Oct 31, since the Monday snapshot doesn't exist yet).
