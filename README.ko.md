한국어 | [English](README.md)

# Football News

축구 팀의 소식을 수집 후 뉴스레터를 생성해 매주 이메일로 발송하는 구독자에게 전송하는 서비스

**대시보드:** https://8804who.github.io/FootballNews/

## 워크 플로우

1. **수집** — FotMob과 Google News RSS에서 지정된 프리미어리그 구단들의 경기 리포트와 이적 소식을 매일 수집
2. **생성** — 최근 7일간 수집된 데이터를 바탕으로 이용해 구단별 뉴스레터 생성
3. **평가** — 생성된 뉴스레터를 원본 데이터와 대조해 성능 평가 수행
4. **발송** — 구독자에게 뉴스레터 발송
5. **게시** — 구독자 수, 워크플로우 상태, 평가 점수 이력 확인 용 대시보드 생성 및 배포

## 아키텍처


```
1) collect_news.py  (매일 00:30 UTC)
     ├─ scrappers/fotmob.py    → Playwright로 FotMob 경기 페이지 렌더링 + API 호출
     │                            → 이벤트/스탯/교체/골/카드 등 파싱
     └─ scrappers/news_rss.py  → Google News RSS 파싱
     → team_daily_report_{team}_{matches,transfers}.md / team_daily_report_{team}.md 생성
     → gs://my-football-news/football-news/datas/{fotmob,news_rss}/YYYYMMDD/ 업로드

2) generate_newsletter.py  (매주 월 01:00 UTC)
     GCS에서 최근 7일치 fotmob + news_rss 데이터 다운로드
     └─ summarizers/llm.py (LLMSummarizer)
          → LangChain FewShotPromptTemplate + ChatOpenAI
          → prompt.yml(시스템/섹션 프롬프트) + example.yml(few-shot 예시) 참고하여
            구단 별 뉴스레터 생성
     └─ evaluate/evaluate_main.py 뉴스레터를 원본 데이터와 비교하여 성능 평가
     → newsletter/, evaluation/ 데이터를 GCS에 업로드

3) send_mail.py  (매주 월 02:00 UTC, generate 약 1시간 뒤)
     GCS에서 이번 주 뉴스레터 다운로드
     ├─ google_sheet_parser.py      → "신청자 목록" 시트에서 구단별 구독자 이메일 추출
     └─ email_sender/smtp_sender.py → Gmail SMTP로 발송

4) generate_dashboard.py  (collect_news / generate_newsletter 완료 후 트리거)
     GCS에서 구독자 수, 워크플로우 실행 이력, 평가 점수 이력을 취합
     └─ dashboard/render.py → 대시보드 생성 → GitHub Pages 배포
```

## 코드 구조

```
config.py               설정 정보

scrappers/
  fotmob.py              Playwright로 FotMob 경기 페이지에서 이벤트/통계/교체/득점/카드를 추출합니다.
  news_rss.py             Google RSS 뉴스 수집
  fbref.py, fpl.py         사용하지 않음

summarizers/
  llm.py                  뉴스레터 생성

evaluate/                 생성된 뉴스레터를 fotmob 원본 데이터와 대조해 성능 평가
    score_accuracy.py        30% — 뉴스레터 내 스코어가 원본과 일치하는지
    section_completeness.py  20% — 4개 필수 섹션이 모두 채워졌는지
    llm_drift.py              15% — 모델이 챗봇 모드로 이탈하지 않았는지
    hallucination.py          25% — 원본에 없는 선수명을 지어내지 않았는지
    language_compliance.py    10% — 한국어 비율이 기준치(80%) 이상인지
  utils.py                 날짜 파싱, lookback 윈도 계산 등 공용 로직


email_sender/
  email_sender.py          EmailSender 추상 클래스
  smtp_sender.py            Gmail SMTP + markdown-it-py로
                          Markdown을 HTML로 변환 후 전송

dashboard/
  render.py                수집된 통계(구독자 수, 워크플로우 상태, 평가 이력)를
                           HTML로 렌더링 후 대시보드 화면 구축

tests/                    단위 테스트
```

### 설정 계층

`config.py`는 모듈이 임포트되는 시점에 아래 파일들을 순서대로 읽어 상수로 노출합니다.

| 파일 | 용도 |
|---|---|
| `api.yml` | API 키/인증정보(Github Workflow에서는 Github Secrets 사용) |
| `setting.yml` | 대상 구단 목록과 사용할 LLM 모델 |
| `prompt.yml` | LLM 시스템 프롬프트 및 작업별 프롬프트 |
| `example.yml` | 뉴스레터 작성 few-shot |
| `teams.yml` | FotMob 팀 정보(ID, 팀명) 매핑 정보 |

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

# 뉴스레터 생성
python generate_newsletter.py

# 성능 평가
python evaluate/evaluate_main.py
python evaluate/evaluate_main.py --date 20260306
python evaluate/evaluate_main.py --team Liverpool

# 뉴스레터 발송
python send_mail.py

# 대시보드 생성
python generate_dashboard.py
```

## 자동화

| 워크플로우 | 스케줄 | 내용 |
|---|---|---|
| `collect_news.yaml` | 매일 00:30 UTC (09:30 KST) | 수집 후 GCS 업로드 |
| `generate_newsletter.yaml` | 월요일 01:00 UTC (10:00 KST) | 7일치 다운로드 → 생성 → 평가 → 업로드 |
| `send_mail.yaml` | 월요일 02:00 UTC (11:00 KST) | 이번 주 뉴스레터 다운로드 → 발송 |
| `dashboard.yaml` | `collect_news`/`generate_newsletter` 완료 후 | 상태 대시보드 재생성 및 배포 |

필요한 GitHub Secrets: `OPENAI_API_KEY`, `GCP_SA_KEY`, `GOOGLE_CLOUD_EMAIL`, `GOOGLE_CLOUD_SPREADSHEET_URL`, `SMTP_USERNAME`, `SMTP_PASSWORD`.
