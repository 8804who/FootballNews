한국어 | [English](README.md)

# Football News

축구 팀의 소식을 수집 후 뉴스레터를 생성해 매주 이메일로 발송하는 구독자에게 전송하는 서비스

## 워크 플로우

1. **수집** — FotMob과 Google News RSS에서 지정된 프리미어리그 구단들의 경기 리포트와 이적 소식을 매일 수집. 매 실행이 최근 3일을 다시 수집하므로, 하루 수집이 실패해도 다음 실행이 채움
2. **생성** — 매주 월요일 아침 수집이 성공하면, 직전 한 주(월요일 00:00 UTC → 다음 월요일 00:00 UTC)의 구단별 뉴스레터 생성. 경기와 기사는 킥오프/발행 시각 기준으로 골라 한 번씩만 실림
3. **평가** — 생성된 뉴스레터를 원본 데이터와 대조해 평가(스코어, 분 단위 경기 사실, 각 기사 항목과 링크한 원문 비교, 의미를 보는 LLM 판정기)하고 토큰·비용을 기록. 이어서 호마다 예/아니오 점검(틀리거나 빠지거나 반복된 경기, 다른 구단 소식, 엉뚱한 링크)을 수행. 점검 결과는 발송을 막지 않고 대시보드에 표시
4. **발송** — 모든 구단의 뉴스레터를 구독자에게 발송. 수신거부한 주소와 이미 이번 호를 받은 구독자는 제외. 발송을 멈추거나 실패로 만드는 건 파이프라인 오류(단계 실패, 파일 누락, 발송 실패)뿐
5. **게시** — 구독자 수, 워크플로우 상태, 평가 점수 이력, 호별 점검 결과 확인 용 대시보드 생성 및 배포

## 아키텍처


```
1) collect_news.py  (매일 00:30 UTC)
     ├─ scrappers/fotmob.py    → Playwright로 FotMob 경기 페이지 렌더링 + API 호출
     │                            → 이벤트/스탯/교체/골/카드 등 파싱, 전체 경기 일정도 저장
     └─ scrappers/news_rss.py  → Google News RSS 파싱 (발행 시각 보존, 구단 목록 페이지 제외)
     → team_daily_report_{team}_{matches,transfers}.md + _fixtures.json / team_daily_report_{team}.md 생성
     → gs://my-football-news/football-news/datas/{fotmob,news_rss}/YYYYMMDD/ 업로드
     → 월요일이면 generate_newsletter 시작

2) generate_newsletter.py  (월요일, collect_news가 시작)
     GCS에서 지난 월요일부터 오늘까지의 수집 폴더 다운로드
     ├─ edition.py   → 이번 주 경기/이적/기사를 킥오프·발행 시각 기준으로 한 번씩 선택,
     │                 이미 치러진 경기의 프리뷰 기사는 제외
     └─ summarizers/llm.py (LLMSummarizer)
          → ChatOpenAI. prompt.yml 규칙은 시스템 메시지, example.yml few-shot 예시는
            이전 대화 턴, 실제 입력은 마지막 메시지로 전달
          → 모델은 기사를 [N1], [N2]…로 인용하고, summarizers/citations.py가
            이 태그를 수집한 기사 링크로 바꿈
     └─ evaluate/evaluate_main.py → report.md + summary.json (지표 v2, 판정기 포함, usage.json 기반 비용)
     └─ evaluate/gate.py          → 예/아니오 점검 → gate.json, 대시보드에 표시 (발송은 막지 않음)
     → newsletter/, evaluation/ 데이터를 GCS에 업로드 후 send_mail 시작

3) send_mail.py  (generate_newsletter가 시작)
     GCS에서 이번 주 뉴스레터(sent.json 포함) 다운로드
     ├─ google_sheet_parser.py      → "신청자 목록" 시트에서 구단별 구독자 이메일 추출
     │                                 ("수신거부" 시트의 주소는 제외)
     └─ email_sender/smtp_sender.py → 수신거부 링크가 담긴 하단 안내와 함께 Gmail SMTP로 발송
     → 이번 호를 받은 구독자를 sent.json에 기록해, 다시 실행해도 중복 발송하지 않음

4) generate_dashboard.py  (collect_news / generate_newsletter / send_mail 완료 후 트리거)
     GCS에서 구독자 수, 워크플로우 실행 이력, 평가 점수 이력, 호별 점검 결과를 취합
     └─ dashboard/render.py → 대시보드 생성 → GitHub Pages 배포
```

## 코드 구조

```
config.py               설정 정보
edition.py              주간 호에 들어갈 경기와 기사 선택
team_names.py           구단 이름 표기("Man Utd", "Spurs", "토트넘")를 teams.yml 기준으로 통일
notify.py               워크플로우가 실패하면 운영자에게 알림 메일 발송

scrappers/
  fotmob.py              Playwright로 FotMob 경기 페이지에서 이벤트/통계/교체/득점/카드를 추출합니다.
  news_rss.py             Google RSS 뉴스 수집
  fbref.py, fpl.py         사용하지 않음

summarizers/
  llm.py                  뉴스레터 생성
  citations.py            모델의 [N1] 출처 태그를 기사 링크로 변환

evaluate/                 생성된 뉴스레터를 fotmob / RSS 원본 데이터와 대조해 성능 평가 (지표 v2)
    score_accuracy.py        20% — 스코어보드의 모든 행이 맞는지 (반복·창작 경기는 감점)
    match_facts.py           15% — "몇 분에 누가" 주장이 경기 이벤트와 맞는지
    news_grounding.py         15% — 각 뉴스 항목이 링크한 원문 기사와 맞는지
    hallucination.py          15% — 어떤 원본에도 없는 이름을 지어내지 않았는지
    section_completeness.py  10% — 이번 주 원본에 맞는 섹션이 있는지
    language_compliance.py    10% — 스타일 가이드상 영어로 쓰는 고유명사를 뺀 본문이
                                     한국어인지 (기준 95%)
    llm_drift.py               5% — 모델이 챗봇 모드로 이탈하지 않았는지
    judge.py                  10% — LLM 판정기: 각 항목이 원본과 같은 뜻인지 (--judge)
  gate.py                  호별 예/아니오 점검. 결과는 대시보드에 표시하고 발송은 막지 않음
  cost.py, pricing.yml     토큰 사용량 → 비용 (모델별 가격, 직접 갱신)
  harness.py, runs.yml     과거 호로 프롬프트·모델 변형 비교
  backfill.py              지표를 바꾼 뒤 과거 주를 다시 채점
  golden.py                실제 호를 회귀 테스트 사례로 고정 (tests/golden/)
  utils.py                 파싱, 원본 데이터 로딩 등 공용 로직


email_sender/
  email_sender.py          EmailSender 추상 클래스
  smtp_sender.py            Gmail SMTP + markdown-it-py로
                          Markdown을 HTML로 변환 후 전송

dashboard/
  render.py                수집된 통계(구독자 수, 워크플로우 상태, 평가 이력)를
                           HTML로 렌더링 후 대시보드 화면 구축

tests/                    단위 테스트 (python -m unittest discover -s tests)
```

### 설정 계층

`config.py`는 모듈이 임포트되는 시점에 아래 파일들을 순서대로 읽어 상수로 노출합니다.

| 파일 | 용도 |
|---|---|
| `api.yml` | API 키/인증정보(Github Workflow에서는 Github Secrets 사용), 선택 항목 `ALERT_EMAIL` |
| `setting.yml` | 대상 구단 목록, 사용할 LLM 모델, 메일 하단 링크(`newsletter.signup_url`, `newsletter.unsubscribe_url`) |
| `prompt.yml` | LLM 시스템 프롬프트 및 작업별 프롬프트 |
| `example.yml` | 뉴스레터 작성 few-shot (가상의 이름만 사용) |
| `teams.yml` | FotMob 팀 정보(ID, 팀명) 매핑 정보, 구단별 다른 표기(`aliases`) |

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 사용법

```bash
# 구단 별 데이터 수집
python collect_news.py
python collect_news.py --team Arsenal

# 뉴스레터 생성 (이번 주 월요일 호)
python generate_newsletter.py
python generate_newsletter.py --date 20261026 --team Chelsea   # 한 구단의 호를 다시 생성

# 성능 평가
python evaluate/evaluate_main.py
python evaluate/evaluate_main.py --date 20260306
python evaluate/evaluate_main.py --team Liverpool
python evaluate/evaluate_main.py --date 20261102 --judge \
  --json-output datas/evaluation/20261102/summary.json      # CI가 실행하는 형태

# 과거 호로 프롬프트·모델 변형 비교 (evaluate/runs.yml)
python evaluate/harness.py --judge                           # → evaluate/runs/report.md
python evaluate/harness.py --rescore --judge                 # 지표 변경 후, 재생성 없이 다시 채점

# 지표를 바꾼 뒤 과거 주 다시 채점 (로컬, --upload 시 대시보드 반영)
python evaluate/backfill.py

# 새로 발견한 오류를 회귀 테스트 사례로 추가
python evaluate/golden.py --name <사례> --date <YYYYMMDD> --team <팀> --why "<무엇이 틀렸나>"

# 호별 점검, 발송은 막지 않음 (대시보드용 datas/newsletter/{date}/gate.json 생성)
python evaluate/gate.py --date 20261026

# 뉴스레터 발송
python send_mail.py --dry-run               # 발송 대상만 출력
python send_mail.py

# 대시보드 생성
python generate_dashboard.py

# 테스트
python -m unittest discover -s tests
```

## 자동화

| 워크플로우 | 실행 | 내용 |
|---|---|---|
| `collect_news.yaml` | 매일 00:30 UTC (09:30 KST) | 수집 후 GCS 업로드, 월요일이면 `generate_newsletter` 시작 |
| `generate_newsletter.yaml` | 월요일 `collect_news`가 시작 (또는 수동) | 생성 → 평가 → 호별 점검(발송은 막지 않음) → 업로드 → `send_mail` 시작 |
| `send_mail.yaml` | `generate_newsletter`가 시작 (또는 수동) | 모든 구단 발송 (이미 받은 구독자는 제외) |
| `dashboard.yaml` | 위 워크플로우 완료 후 | 상태 대시보드 재생성 및 배포 (주마다 저장된 summary.json, gate.json 사용) |
| `tests.yaml` | 모든 push, pull request | 단위 테스트 + 골든 회귀 사례 (시크릿 불필요) |

세 워크플로우를 각자의 스케줄 대신 하나로 연결해, 주말 경기가 수집되기 전에 뉴스레터가 생성되는 일이 없도록 했습니다. GitHub의 스케줄 실행은 몇 시간씩 늦게 시작되므로(2026년 10월 기준 약 5시간) 전체 흐름도 그만큼 늦게 시작됩니다.

필요한 GitHub Secrets: `OPENAI_API_KEY`, `GCP_SA_KEY`, `GOOGLE_CLOUD_EMAIL`, `GOOGLE_CLOUD_SPREADSHEET_URL`, `SMTP_USERNAME`, `SMTP_PASSWORD`. 선택: `ALERT_EMAIL` (알림 받을 주소, 기본값은 `SMTP_USERNAME`).

## 문제가 생겼을 때

워크플로우가 실패하면 운영자에게 메일이 갑니다. 내용 문제로는 발송이 멈추지 않습니다.

- **대시보드에 구단이 표시됨** — 그 구단의 카드에 이유가 있습니다: 틀리거나 빠지거나 반복된 경기, 끝났는데 수집되지 않은 경기, few-shot 예시 문구, 다른 구단의 소식, 이 구단의 기사가 아닌 링크. 해당 호는 이미 발송됐으니, 다음 주 전에 원인을 고치세요(`--date`/`--team`으로 다시 생성해 로컬에서 확인하면 편합니다).
- **월요일 수집 실패** — 수집이 성공할 때까지 뉴스레터를 만들지 않습니다. `collect_news`를 다시 실행하거나(월요일이면 뉴스레터도 다시 시작), `send_after`를 체크하고 `generate_newsletter`를 실행하세요.
- **일부 메일 발송 실패** — `send_mail`을 다시 실행하세요. `sent.json` 덕분에 이미 받은 구독자에게는 다시 보내지 않습니다.
- **수신거부** — 모든 메일에 수신거부 링크와 `List-Unsubscribe` 헤더가 있습니다. 기본값은 발신 주소로 메일을 보내는 방식이고, `setting.yml`의 `newsletter.unsubscribe_url`에 Google Form 주소를 넣으면 그 폼을 씁니다(`{email}`은 자동으로 채워짐). 구독자 스프레드시트의 "수신거부" 시트에 있는 주소로는 발송하지 않습니다.
- **개인정보** — 이 저장소는 공개 저장소라 워크플로우 로그도 공개됩니다. `send_mail.py`는 마스킹한 주소(`j***@gmail.com`)만 로그에 남깁니다.
