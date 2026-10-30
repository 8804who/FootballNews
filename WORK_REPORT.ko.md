# 평가 파이프라인 개선 작업 보고서 (2026-10-30)

모든 변경은 아직 커밋하지 않은 상태입니다. 워크플로 변경은 `main`에 push해야 적용됩니다. 직전 작업(발송 전 점검, 수집·발송 수정 등)은 `PRODUCT_PLAN.md`의 Progress 절에 정리되어 있습니다.

## 요약

- **이름만 보던 평가가 사실을 확인합니다.** 몇 분에 누가 골을 넣었는지, 기사 항목이 링크한 원문과 같은 뜻인지(LLM 판정기)까지 봅니다.
- **모든 호를 평가합니다.** 뉴스만 있던 주(예: 10월 26일 Chelsea)도 포함합니다. 수집이 빠진 주를 드러내도록 **커버리지**를 점수 옆에 표시합니다.
- **호별 토큰과 비용**을 기록합니다.
- 프롬프트×모델을 숫자로 비교하는 **실험 하네스**를 만들어 실제로 돌렸습니다. 지표 오탐을 고친 뒤 다시 채점까지 했습니다.
- 매주 **버전이 붙은 평가 결과(`summary.json`)를 저장**합니다. 대시보드는 저장된 결과를 읽고, 같은 버전끼리만 추세를 그립니다. 과거 주는 백필 도구로 다시 채점합니다.
- 실제로 구독자에게 나간 오류 6건과 정상 호 1건을 **골든 회귀 테스트**로 고정했습니다. push마다 테스트가 돌도록 CI도 추가했습니다(테스트 79개 통과).
- README, README.ko, CLAUDE.md를 v2 평가 기준으로 갱신했습니다.

## 1. 무엇을 했고, 왜 했나

| 작업 | 왜 |
| --- | --- |
| 새 지표 **Match Facts** (`evaluate/match_facts.py`) | 스코어가 맞아도 "56분 추가골"을 엉뚱한 선수 몫으로 쓰는 오류는 잡지 못했습니다. 실제로 8월 31일 Man United 호는 Jacob Greaves의 자책골을 Bruno의 해트트릭에 포함해 발송했습니다. |
| Match Facts의 **절(節) 단위 짝짓기** | 처음에는 분을 "가장 가까운 이름"과 짝지었습니다. 그 결과 모델 비교에서 실패로 잡힌 5건이 모두 오탐이었습니다. 예: "79분**까지** 밀렸지만", "44분 먼저 **실점**", "8', 10'에 앞섰지만 … Kostoulas가". 이제는 한국어 문장 구조를 따릅니다. 분 바로 뒤의 이름, 없으면 조사로 이어진 바로 앞의 이름(Ramón**의** 76분), 없으면 같은 절의 주어(…Bruno**가** 해트트릭)와 짝짓고, 이름이 없는 절의 분은 검사하지 않습니다. |
| **News Grounding** 강화 | 지금까지는 기사 항목을 그 주의 아무 헤드라인과나 비교했습니다. 이제는 항목이 **링크한 바로 그 기사**와 비교합니다. |
| **LLM 판정기 Faithfulness** (`evaluate/judge.py`, `--judge`) | 정규식은 뜻이 뒤집힌 것을 보지 못합니다. 예: "Gyokeres keen to leave Arsenal"을 "Arsenal로 이적을 원한다"로 쓴 경우, 이긴 경기를 "지키지 못했다"로 쓴 경우. 같은 질문에 3번 답하게 해서 다수결로 정합니다. |
| **경기 결과 줄** (`edition.with_result_line`) | 원본 스코어는 항상 홈-원정 순서라서 모델이 원정 경기를 거꾸로 읽었습니다. 8월 31일 첼시 호가 그랬고, 판정기 후보 모델도 같은 실수를 했습니다. 이제 `Result: Fulham 2 - 3 Chelsea (Chelsea won)` 줄로 승패를 명시합니다. |
| **Score Accuracy**가 반복·창작 경기도 감점 | 지난주 경기를 다시 실어도 100%가 나왔습니다. 이제는 맞은 행 ÷ (원본 경기 수 + 원본에 없는 행)으로 계산합니다. |
| **섹션 완결성**을 원본 기준으로 판단 | 경기가 없는 주에도 경기 섹션을 요구해서, 뉴스만 있는 주는 통과할 수 없었습니다. |
| **커버리지** 표시 | 수집이 실패한 10월 26일 주가 오히려 점수가 가장 높았습니다. 지표는 주어진 원본에 충실한지만 재기 때문입니다. FotMob 일정과 대조한 수집률을 점수 옆에 따로 표시합니다. |
| **토큰·비용 기록** (`usage.json`, `evaluate/pricing.yml`, `evaluate/cost.py`) | 5월 office-hours 설계 문서의 1번 과제였습니다. |
| **실험 하네스** (`evaluate/harness.py`, `evaluate/runs.yml`, `--rescore`) | 같은 설계 문서의 2번 과제입니다. 과거 데이터로 재생성하며 업로드·발송은 하지 않습니다. `--rescore`는 지표를 바꾼 뒤 재생성 없이 다시 채점합니다. |
| **버전 있는 평가 기록** (`METRICS_VERSION`, `summary.json`, `evaluate/backfill.py`) | 대시보드가 그날의 코드로 매일 다시 채점해서 CI 리포트와 값이 달랐습니다. 지표가 바뀌면 추세선도 서로 다른 기준이 섞였습니다. |
| **골든 회귀 테스트** (`tests/golden/`, `evaluate/golden.py`), **CI 테스트** (`tests.yaml`) | 평가기 자체를 검증하기 위해서입니다. 별칭 처리나 교차 구단 검사를 일부러 끄면 해당 사례가 실패하는 것을 확인했습니다. |
| **`reasoning_effort` 설정** (`setting.yml`, 기본 꺼짐) | 비교 결과 가장 좋은 조합(gpt-5.4-mini + 추론 low)을 코드 수정 없이 설정 한 줄로 쓸 수 있게 했습니다. 지금 운영 동작은 그대로입니다. |

가중치는 v2입니다(합계 100%).

| 지표 | 가중치 |
| --- | --- |
| Score Accuracy | 20% |
| Match Facts | 15% |
| News Grounding | 15% |
| No Hallucination | 15% |
| Section Completeness | 10% |
| Language | 10% |
| No Drift | 5% |
| Faithfulness | 10% |

측정할 수 없는 지표는 빼고 나머지로 다시 정규화합니다. 매주 CI는 판정기까지 켜서 실행합니다(호당 약 $0.01).

## 2. 실행 결과

### 보정 (실제 호 78개)

**Match Facts**
- 원본이 온전한 주에서 실패로 잡힌 것은 모두 실제 문제였습니다.
  - 지난주 경기를 반복하며 넣은 사실 18건
  - 자책골 오기 1건
- 오탐은 0건입니다.

**판정기 선정**
- 알려진 6사례에 대해 3표 다수결로 두 번 돌렸습니다.
  - gpt-5-mini: 두 번 모두 6/6
  - gpt-5.4-mini: 결과 줄을 넣어도 원정 승리를 패배로 읽어 5/6
- 기본 판정기는 gpt-5-mini입니다.

### 모델 비교 (지표 수정 후 다시 채점한 최종본)

- 대상: 2026-09-21과 2026-10-19 두 주, 구단 6개, 12개 호.
- 판정기는 켰습니다.

| | gpt-5-mini (현재) | gpt-5.4-nano | gpt-5.4-mini | gpt-5.4-mini + 추론 low | gpt-5.6-terra |
| --- | --- | --- | --- | --- | --- |
| 종합 | 99.0% | 98.4% | 98.7% | **99.6%** | 99.1% |
| Match Facts | 100% | 100% | 100% | 100% | 100% |
| News Grounding | 95.8% | 93.6% | 97.2% | **100%** | 97.7% |
| Faithfulness (판정기) | 100% | 95.3% | 93.2% | 97.8% | 97.6% |
| 한국어 비율 경고 | 4건 | 1건 | 0건 | 1건(95%) | 0건 |
| 발송 보류 | 0/12 | 0/12 | 0/12 | 0/12 | 0/12 |
| 호당 비용 | $0.0117 | **$0.0017** | $0.0059 | $0.0068 | $0.0192 |
| 호출당 시간 | 29.0초 | 3.1초 | 2.7초 | 3.1초 | 8.0초 |

**해석할 때 주의할 점**

- 첫 채점에서는 Match Facts가 모델마다 달랐습니다. 5건을 원문과 대조해 보니 모두 지표의 짝짓기 오탐이었고, 고친 뒤에는 모든 모델이 100%입니다. 실제 경기 사실 오류는 없었습니다.
- **판정기 점수는 같은 출력에서도 실행마다 최대 ±3.4점 바뀌었습니다.** 예: gpt-5.4-mini는 96.6 → 93.2. 그래서 4점 미만 차이는 잡음으로 봐야 합니다.
- 판정기가 현재 생성 모델과 같은 gpt-5-mini여서, 현재 모델의 100%에는 자기 편향이 섞였을 수 있습니다.
- 현재 모델은 한국어 비율 경고(91~93%)가 가장 많습니다. 영어 단어를 더 많이 섞어 씁니다.

**결론(잠정)**
- **gpt-5.4-mini + reasoning low**가 가장 좋습니다.
  - 종합 99.6%, 뉴스 근거 100%
  - 비용 약 42% 절감, 9배 빠름, 보류 0건
- 다른 주를 2~3주 더 하네스로 확인한 뒤 `setting.yml`에서 `model: gpt-5.4-mini`와 `reasoning_effort: low`로 바꾸는 것을 권합니다.
- gpt-5.4-nano는 비용이 1/7이지만 뉴스 근거와 판정기 점수가 다소 낮습니다.
- gpt-5.6-terra는 가장 비싸고 이득이 없습니다.

**이번 작업에 쓴 OpenAI 비용**: 약 $1.9

| 항목 | 비용 |
| --- | --- |
| 하네스 생성 | $0.54 |
| 판정기 2회 | $1.18 |
| 보정·시험 호출 | 약 $0.15 |

### 백필 (지표 v2, 판정기 끔, 로컬에만 저장)

| 주 | 종합 |
| --- | --- |
| 03-30 | 60.0% |
| 08-03 | 71.8% |
| 08-24 | 79.2% |
| 08-31 | 85.9% |
| 09-07 | 89.2% |
| 09-14 | 87.5% |
| 09-21 | 91.1% |
| 09-28 | 79.7% |
| 10-05 | 81.1% |
| 10-12 | 91.1% |
| 10-19 | 88.1% |
| 10-26 | 94.2% |

- 3주는 원본 폴더가 내려받아져 있지 않아 건너뛰었습니다.
- 10월 26일이 높은 것은 그 주 원본 자체에 주말 경기가 없었기 때문입니다. 10월 30일부터 경기 일정 목록을 저장하므로, 앞으로는 커버리지와 발송 전 점검이 이런 주를 잡습니다.
- GCS와 대시보드에는 반영하지 않았습니다. `python evaluate/backfill.py --upload`로 반영하면 공개 대시보드의 추세가 v2 기준으로 바뀝니다.

## 3. 바뀐 파일

**새 파일**
- `evaluate/match_facts.py`
- `evaluate/judge.py`
- `evaluate/cost.py`
- `evaluate/pricing.yml`
- `evaluate/harness.py`
- `evaluate/runs.yml`
- `evaluate/backfill.py`
- `evaluate/golden.py`
- `tests/golden/*.json` (7개)
- `tests/test_golden.py`
- `tests/test_evaluation_v2.py`
- `.github/workflows/tests.yaml`
- 이 문서

**수정한 파일**
- 평가: `evaluate/evaluate_main.py`, `evaluate/score_accuracy.py`, `evaluate/news_grounding.py`, `evaluate/section_completeness.py`, `evaluate/gate.py`, `evaluate/utils.py`
- 생성: `edition.py`, `summarizers/llm.py`, `generate_newsletter.py`, `prompt.yml`, `config.py`, `setting.yml`
- 대시보드와 CI: `generate_dashboard.py`, `.github/workflows/generate_newsletter.yaml`, `.gitignore`
- 문서: `README.md`, `README.ko.md`, `CLAUDE.md`, `PRODUCT_PLAN.md`(표 안 HTML 목록 정리)

## 4. 남은 일

1. **커밋과 push.** 워크플로 변경은 push 후 적용됩니다.
2. **`backfill.py --upload` 여부 결정.** 공개 대시보드 추세가 v2 기준으로 바뀝니다.
3. **판정기 자기 편향 점검.** `--judge-model`을 다른 모델로 바꿔 `harness.py --rescore --judge`를 한 번 더 실행해 보세요.
4. **모델 전환.** 2~3주 더 비교한 뒤 `setting.yml`에서 `model`과 `reasoning_effort`를 바꾸면 됩니다.
5. **Match Facts의 의도된 한계.** 이름이 없는 절의 분(예: "61·68분 연속 득점")은 검사하지 않습니다. 오탐 대신 일부 누락을 택했습니다.
6. **`TODOS.md`는 손대지 않았습니다.** #2와 #4는 완료, #1은 대부분 완료입니다.

## 5. 사용법

```bash
python evaluate/evaluate_main.py --date 20261102 --judge --json-output datas/evaluation/20261102/summary.json
python evaluate/harness.py --judge                       # runs.yml의 모델·날짜 비교 → evaluate/runs/report.md
python evaluate/harness.py --rescore --judge             # 지표 변경 후 재생성 없이 다시 채점
python evaluate/backfill.py [--upload]                   # 과거 주를 현재 지표로 다시 채점
python evaluate/golden.py --name <이름> --date <날짜> --team <팀> --why "<무엇이 틀렸나>"
python -m unittest discover -s tests
```
