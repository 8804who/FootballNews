import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import edition
from edition import NewsItem
from evaluate import cost, judge, match_facts, news_grounding, section_completeness

UTC = timezone.utc

MU_BLOCK = """## 🏟️ Match: vs Ipswich
- **Competition:** Premier League
- **Date:** 2026-08-29 14:00
- **Venue:** Home
- **Score:** 5 - 2
- `29'` **Ipswich**:  - ⚽ Goal: Leif Davis (0 - 1) (assist by Abdul Fatawu)
- `40'` **Man United**:  - ⚽ Goal: Bruno Fernandes (1 - 1) (assist by Matheus Cunha)
- `56'` **Man United**:  - ⚽ Goal: Jacob Greaves (2 - 1) (assist by Own goal)
- `61'` **Man United**:  - ⚽ Goal: Bruno Fernandes (3 - 1) (assist by Penalty)
- `68'` **Man United**:  - ⚽ Goal: Bruno Fernandes (4 - 1) (assist by None)
- `75'` **Man United**:  - 🔄 Player Substitution: Bryan Mbeumo -> Amad Diallo
- `90+1'` **Ipswich**:  - ⚽ Goal: Chuba Akpom (5 - 2) (assist by Julio Enciso)
---
"""


def edition_text(story: str, headline: str = "**헤드라인입니다**") -> str:
    return f"# MU\n\n## 🏆 이번 주 헤드라인\n{headline}\n\n## ⭐ 이번 주 베스트 경기\n{story}\n\n## 🔁 이적 & 뉴스\n- 뉴스\n"


class MatchFactsTest(unittest.TestCase):
    def test_correct_minutes_and_players_pass(self):
        story = "Bruno Fernandes가 40분 동점골을 넣었고 61분, 68분에도 골망을 흔들었습니다. 후반 30분 교체된 Amad Diallo도 활기를 더했습니다."
        result = match_facts.evaluate(edition_text(story), [MU_BLOCK])
        self.assertEqual(result["failed"], [])
        self.assertEqual(result["score"], 1.0)

    def test_own_goal_credited_to_the_wrong_player_fails(self):
        # The sent Aug 31 edition: the 56' goal was Jacob Greaves' own goal.
        story = "40분 Bruno Fernandes의 동점골을 시작으로 56분 추가골과 61·68분 연속 득점으로 Bruno가 해트트릭을 완성했습니다."
        result = match_facts.evaluate(edition_text(story), [MU_BLOCK])
        self.assertEqual(len(result["failed"]), 1)
        self.assertIn("56' Bruno", result["failed"][0])

    def test_a_minute_borrows_no_name_from_another_clause(self):
        # Harness false alarms: the minutes belong to a team or a conceded goal.
        story = ("전반 8', 10'에 빠르게 앞섰지만 전반 추가시간 Bruno Fernandes가 추격골을 넣었습니다. "
                 "79분까지 0-3으로 밀렸지만, Amad Diallo가 추격했습니다. 전반 44분 먼저 실점했지만 Bruno Fernandes가 반격했습니다.")
        self.assertEqual(match_facts.extract_claims(edition_text(story), [MU_BLOCK]), [])

    def test_durations_conceded_goals_and_the_headline_are_not_claims(self):
        story = ("초반 29분 실점으로 끌려갔지만 Bruno Fernandes가 반격했습니다. "
                 "7분 사이에 두 골이 터졌고 Bruno Fernandes는 3분 뒤 쐐기를 박았습니다.")
        headline = "**초반 2분의 충격을 뒤집은 Bruno Fernandes**"
        result = match_facts.evaluate(edition_text(story, headline), [MU_BLOCK])
        self.assertEqual((result["checked"], result["failed"]), (0, []))

    def test_someone_not_in_the_match_fails(self):
        story = "Kevin De Bruyne가 75분에 결승골을 넣었습니다."
        self.assertIn("not in this week's match events", match_facts.evaluate(edition_text(story), [MU_BLOCK])["failed"][0])

    def test_no_events_means_unmeasured(self):
        self.assertIsNone(match_facts.evaluate(edition_text("Bruno가 40분에 골"), [])["score"])


class ResultLineTest(unittest.TestCase):
    def test_away_win_is_spelled_out(self):
        block = "## 🏟️ Match: vs Fulham\n- **Date:** 2026-08-24 19:00\n- **Venue:** Away\n- **Score:** 2 - 3\n---\n"
        self.assertIn("- **Result:** Fulham 2 - 3 Chelsea (Chelsea won)", edition.with_result_line(block, "Chelsea"))

    def test_home_loss_and_draw(self):
        home = "## 🏟️ Match: vs Brighton\n- **Venue:** Home\n- **Score:** 0 - 1\n"
        draw = "## 🏟️ Match: vs Fleetwood\n- **Venue:** Away\n- **Score:** 1 - 1\n"
        self.assertIn("(Arsenal lost)", edition.with_result_line(home, "Arsenal"))
        self.assertIn("(Arsenal drew)", edition.with_result_line(draw, "Arsenal"))


class CoverageTest(unittest.TestCase):
    def test_finished_fixture_without_a_collected_match_is_reported(self):
        start, end = datetime(2026, 10, 19, tzinfo=UTC), datetime(2026, 10, 26, tzinfo=UTC)
        fixtures = [
            {"utc_time": "2026-10-21T19:00:00.000Z", "finished": True, "home": "Bayern", "away": "Arsenal", "score": "2 - 2"},
            {"utc_time": "2026-10-25T14:00:00.000Z", "finished": True, "home": "Arsenal", "away": "Burnley", "score": "2 - 1"},
            {"utc_time": "2026-10-25T16:00:00.000Z", "finished": False, "home": "X", "away": "Arsenal"},
            {"utc_time": "2026-10-18T14:00:00.000Z", "finished": True, "home": "Forest", "away": "Arsenal", "score": "0 - 1"},
        ]
        blocks = ["## 🏟️ Match: vs Bayern\n- **Date:** 2026-10-21 19:00\n"]
        finished, missing = edition.uncollected_fixtures(fixtures, blocks, start, end)
        self.assertEqual(finished, 2)
        self.assertEqual([f["away"] for f in missing], ["Burnley"])


class CitedGroundingTest(unittest.TestCase):
    NEWS = ("## 🔁 이적 & 뉴스\n### 🧪 루머 밀\n"
            "- **Cole Palmer, 2034년까지 계약 연장** (보도) — 설명. ([Sky Sports](https://n/1))\n"
            "- **Reece James, 3개월 결장** (보도) — 설명. ([Sky Sports](https://n/1))\n")
    HEADLINES = {"https://n/1": news_grounding.build_source_words("Cole Palmer signs extension until 2034", set()),
                 "https://n/2": news_grounding.build_source_words("Reece James out for three months", set())}

    def test_an_item_must_match_the_headline_it_links_to(self):
        # Both names are in the week's pool, but the Reece James item links to the Palmer story.
        pool = set().union(*self.HEADLINES.values())
        result = news_grounding.evaluate(self.NEWS, pool, self.HEADLINES)
        self.assertEqual(result["score"], 0.5)
        self.assertIn("Reece James", result["ungrounded"][0])


class SectionCompletenessTest(unittest.TestCase):
    def test_news_only_week_only_needs_the_news_section(self):
        text = "# Chelsea\n\n## 🔁 이적 & 뉴스\n- 뉴스"
        result = section_completeness.evaluate(text, False, has_matches=False, has_news=True)
        self.assertEqual((result["score"], list(result["hits"])), (1.0, ["transfers"]))

    def test_quiet_week_needs_the_rest_week_section(self):
        result = section_completeness.evaluate("# X\n\n## 🌙 이번 주 휴식\n조용했습니다.", False, False, False)
        self.assertEqual(result["score"], 1.0)


class CostTest(unittest.TestCase):
    def test_cost_uses_cached_and_output_rates(self):
        call = {"model": "gpt-5-mini", "input_tokens": 1_000_000, "cached_input_tokens": 200_000, "output_tokens": 100_000}
        # 800k fresh × $0.25 + 200k cached × $0.025 + 100k × $2.00, per million
        self.assertAlmostEqual(cost.call_cost(call), 0.2 + 0.005 + 0.2)

    def test_unpriced_model_gives_no_cost_but_keeps_tokens(self):
        totals = cost.summarize_calls([{"model": "not-a-model", "input_tokens": 10, "output_tokens": 5}])
        self.assertEqual((totals["cost_usd"], totals["input_tokens"]), (None, 10))

    def test_edition_calls_come_from_usage_json_next_to_the_newsletter(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "20261102"
            folder.mkdir()
            (folder / "usage.json").write_text(json.dumps({"teams": {"Manchester United": [{"model": "gpt-5-mini"}]}}))
            self.assertEqual(len(cost.edition_calls(folder / "newsletter_Manchester_United.md")), 1)


class JudgeTest(unittest.TestCase):
    TEXT = ("## ⭐ 이번 주 베스트 경기\nChelsea가 원정에서 승리했습니다.\n\n"
            "## 📊 한눈에 보는 스코어보드\n| 경기 | 스코어 | 한 줄 요약 |\n|---|---|---|\n"
            "| Fulham vs Chelsea | 2-3 | 원정 승리 |\n\n"
            "## 🔁 이적 & 뉴스\n### 🧪 루머 밀\n- **Palmer 재계약** (보도) — 설명. ([Sky Sports](https://n/1))\n")

    def test_story_scoreboard_rows_and_linked_news_are_judged(self):
        items = judge.build_items(self.TEXT, "MATCH DATA", {"https://n/1": "Cole Palmer signs extension - Sky Sports"})
        self.assertEqual([i["kind"] for i in items], ["story", "scoreboard", "news"])
        self.assertEqual(items[2]["source"], "Cole Palmer signs extension - Sky Sports")

    def test_majority_of_three_votes_decides(self):
        votes = iter([
            {1: judge.Verdict(id=1, verdict="SUPPORTED", reason="ok")},
            {1: judge.Verdict(id=1, verdict="CONTRADICTED", reason="wrong")},
            {1: judge.Verdict(id=1, verdict="SUPPORTED", reason="ok")},
        ])
        fake = lambda model, messages: (next(votes), {"model": model, "input_tokens": 1, "output_tokens": 1})
        with patch.object(judge, "_ask", fake), \
             patch.object(judge, "build_items", lambda *a: [{"kind": "news", "text": "x", "source": "y"}]):
            result = judge.evaluate("x", "", {}, model="gpt-5-mini")
        self.assertEqual((result["score"], result["contradicted"], len(result["calls"])), (1.0, [], 3))


class HarnessSummaryTest(unittest.TestCase):
    def test_runs_are_summarized_and_compared_with_the_baseline(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluate"))
        from evaluate import harness
        from evaluate.evaluate_main import WEIGHTS

        def task(run, overall, held=False, model="gpt-5-mini"):
            components = {k: overall for k in WEIGHTS}
            evaluation = {"overall": overall, "components": components, "faithfulness": {"calls": []}}
            gate_result = {"hold": held, "problems": ["wrong score"] if held else [], "warnings": []}
            return {"run": run, "date": "20261019", "team": "Arsenal", "error": None, "eval": evaluation,
                    "gate": gate_result, "calls": [{"model": model, "input_tokens": 1000, "output_tokens": 500, "seconds": 2}]}

        runs = [{"name": "baseline", "model": "gpt-5-mini"}, {"name": "nano", "model": "gpt-5.4-nano"}]
        summaries = {"baseline": harness._summarize([task("baseline", 0.9)]),
                     "nano": harness._summarize([task("nano", 0.8, held=True, model="gpt-5.4-nano")])}
        self.assertEqual(len(summaries["nano"]["held"]), 1)
        report = harness.render_report(runs, summaries, ["20261019"], ["Arsenal"], False, None)
        self.assertIn("80.0% (-10.0)", report)
        self.assertIn("| Held by the pre-send check | 0 / 1 | 1 / 1 |", report)


class HistoryVersionTest(unittest.TestCase):
    def test_a_week_rescored_with_new_metrics_replaces_the_old_entry(self):
        import generate_dashboard as dash
        old = [{"date": "2026-10-19", "overall_score": 72.8, "n": 5}]  # pre-versioning = v1
        summary = {"overall_score": 88.1, "n": 6, "metrics_version": dash.METRICS_VERSION, "metrics": {}}
        history, changed = dash.append_if_new(old, "20261019", summary)
        self.assertTrue(changed)
        self.assertEqual([(h["date"], h["overall_score"]) for h in history], [("2026-10-19", 88.1)])
        self.assertEqual(dash.append_if_new(history, "20261019", summary)[1], False)
        self.assertEqual(len(dash.current_trend(old + [history[0] | {"date": "2026-10-26"}])), 1)


if __name__ == "__main__":
    unittest.main()
