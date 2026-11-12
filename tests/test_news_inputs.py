"""BBC stories, the edition's news selection, the overview snapshot, and the
inputs record the evaluation scores new editions against."""

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import edition
from evaluate import utils
from evaluate.evaluate_main import evaluate_newsletter
from scrappers.news_rss import NewsRSS

UTC = timezone.utc
RUN = datetime(2026, 11, 2, 5, 30, tzinfo=UTC)
START, END = edition.edition_window(RUN)


def rss(*items):
    body = "".join(
        f"<item><title>{t}</title><link>{l}?at_medium=RSS</link><description><![CDATA[{d}]]></description>"
        f"<pubDate>{p}</pubDate></item>" for t, l, d, p in items)
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>BBC</title>{body}</channel></rss>'.encode()


def recent():
    return datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")


class BBCFeedTest(unittest.TestCase):
    def fetch(self, content=None, error=None):
        response = SimpleNamespace(content=content, raise_for_status=lambda: None)
        with patch("scrappers.news_rss.requests.get", side_effect=error, return_value=response) as get:
            items = NewsRSS().get_bbc_team_news("Arsenal", "arsenal")
        self.assertEqual(get.call_args.kwargs["timeout"], 15)
        return items

    def test_keeps_club_stories_with_their_summary(self):
        items = self.fetch(rss(
            ("Dowman to miss three matches", "https://www.bbc.co.uk/sport/football/articles/a1",
             "Arsenal's Max Dowman will miss three matches after an appeal is rejected. More follows.", recent()),
            ("Fleetwood's victory was 'best moment'", "https://www.bbc.co.uk/news/articles/a2",
             "Fleetwood Town beat Arsenal on penalties.", recent()),
            ("'Stutter' penalty back in the spotlight", "https://www.bbc.co.uk/sport/football/articles/a3",
             "Players keep trying it. Arsenal were once involved.", recent()),
            ("Arsenal v Everton live", "https://www.bbc.co.uk/sport/football/live/a4", "Follow it live with Arsenal.", recent()),
        ))
        self.assertEqual([i["title"] for i in items], ["Dowman to miss three matches", "Fleetwood's victory was 'best moment'"])
        self.assertEqual(items[0]["link"], "https://www.bbc.co.uk/sport/football/articles/a1")
        self.assertTrue(items[0]["summary"].startswith("Arsenal's Max Dowman"))

    def test_a_failed_or_unreadable_feed_writes_nothing(self):
        self.assertIsNone(self.fetch(error=requests.exceptions.Timeout("slow")))
        self.assertIsNone(self.fetch(content=b"<html>not a feed"))

    def test_at_most_six_per_run(self):
        many = [(f"Arsenal story {i}", f"https://www.bbc.co.uk/sport/football/articles/b{i}", "Arsenal news.", recent())
                for i in range(9)]
        self.assertEqual(len(self.fetch(rss(*many))), 6)

    def test_a_story_listed_twice_is_kept_once(self):
        # Real Madrid's feed lists every story twice, which used up the six slots.
        many = [(f"Arsenal story {i}", f"https://www.bbc.co.uk/sport/football/articles/b{i}", "Arsenal news.", recent())
                for i in range(4)]
        self.assertEqual([i["title"] for i in self.fetch(rss(*many, *many))],
                         [f"Arsenal story {i}" for i in range(4)])


class DataDir(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if isinstance(text, str) else json.dumps(text), encoding="utf-8")


MATCH = ("## 🏟️ Match: vs Everton\n- **Competition:** Premier League\n- **Date:** 2026-10-31 15:00\n"
         "- **Venue:** Home\n- **Score:** 2 - 0\n- `30'` **Arsenal**:  - ⚽ Goal: Gabriel (1 - 0)\n"
         "- `60'` **Arsenal**:  - ⚽ Goal: Ezri Konsa (2 - 0)\n---\n")


class EditionNewsTest(DataDir):
    def setUp(self):
        super().setUp()
        self.write("news_rss/20261029/team_daily_report_Arsenal_bbc.json", [
            {"title": "Dowman to miss three matches", "link": "https://www.bbc.co.uk/sport/a1",
             "published": "2026-10-29 17:19", "summary": "Max Dowman will miss three matches."}])
        self.write("news_rss/20261029/team_daily_report_Arsenal.md", "## Team: Arsenal\n News Rumors:\n" + "".join(
            f"- [{p}] {t} ({l})\n" for p, t, l in [
                ("2026-10-29 18:00", "Dowman to miss three matches - BBC", "https://news.google.com/g1"),
                ("2026-10-29 18:30", "Dowman ban: Arsenal accept FA decision - BBC Sport", "https://news.google.com/g2"),
                ("2026-10-29 19:00", "Arsenal eye winger - Sky Sports", "https://news.google.com/g3"),
            ]))
        self.write("news_rss/20261102/team_daily_report_Arsenal.md", "## Team: Arsenal\n News Rumors:\n" + "".join(
            f"- [{p}] {t} ({l})\n" for p, t, l in [
                ("2026-11-01 08:00", "Arsenal 2-0 Everton: Konsa and Gabriel move the champions level - Sky Sports", "https://news.google.com/g4"),
                ("2026-11-01 09:00", "Saka out for 2-0 weeks? Arteta updates after Everton win - Sky Sports", "https://news.google.com/g5"),
                ("2026-11-01 10:00", "Arsenal to keep 4-3-3 against Everton - Sky Sports", "https://news.google.com/g6"),
            ]))

    def news(self):
        return edition.edition_news("Arsenal", "Arsenal", START, END, RUN, [MATCH], root=self.root)

    def test_bbc_wins_duplicates_and_google_bbc_items_drop_on_bbc_days(self):
        links = [i.link for i in self.news()]
        self.assertIn("https://www.bbc.co.uk/sport/a1", links)
        self.assertNotIn("https://news.google.com/g1", links)   # same story as BBC's
        self.assertNotIn("https://news.google.com/g2", links)   # Google's BBC item on a BBC day
        self.assertIn("https://news.google.com/g3", links)
        self.assertEqual(self.news()[0].summary, "Max Dowman will miss three matches.")

    def test_only_reports_of_this_weeks_matches_with_their_score_are_dropped(self):
        links = [i.link for i in self.news()]
        self.assertNotIn("https://news.google.com/g4", links)
        self.assertIn("https://news.google.com/g6", links)      # "4-3-3" is not a score

    def test_the_legacy_selection_is_unchanged(self):
        legacy = edition.load_news("Arsenal", "Arsenal", START, END, RUN, root=self.root)
        self.assertIn("https://news.google.com/g4", [i.link for i in legacy])
        self.assertTrue(all(not i.summary for i in legacy))


class OverviewFreshnessTest(DataDir):
    def test_only_a_snapshot_taken_after_the_edition_week_is_used(self):
        self.write("fotmob/20261101/team_daily_report_Arsenal_overview.json", {"collected_at": "2026-11-01T05:30:00Z"})
        self.assertIsNone(edition.load_overview("Arsenal", START, END, RUN, root=self.root))
        self.write("fotmob/20261102/team_daily_report_Arsenal_overview.json", {"collected_at": "2026-11-02T05:30:00Z"})
        self.assertEqual(edition.load_overview("Arsenal", START, END, RUN, root=self.root)["collected_at"],
                         "2026-11-02T05:30:00Z")


NEWSLETTER = """# Arsenal · 주간 뉴스레터 (2026-10-26 ~ 2026-11-01)

## 🏆 이번 주 헤드라인
**Konsa와 Gabriel의 무실점 승리**

## ⭐ 이번 주 베스트 경기
Arsenal이 홈에서 Everton을 2-0으로 이겼습니다. 30분 Gabriel이 먼저 넣었고 60분 Ezri Konsa가 한 골을 더했습니다.

## 📊 한눈에 보는 스코어보드
| 경기 | 스코어 | 한 줄 요약 |
|------|--------|----------|
| Arsenal vs Everton | 2-0 | 두 골 모두 세트피스에서 나왔습니다 |

{blocks}## 🔁 이적 & 뉴스
### ✅ 확정 소식
- **Max Dowman, 세 경기 결장** (보도)
  항소가 기각되면서 Max Dowman이 세 경기에 나서지 못합니다. ([BBC](https://www.bbc.co.uk/sport/a1))
"""
BLOCK = "## 📍 현재 순위\n\n**2위 · 9경기 승점 24**\n\n| 순위 | 팀 | 경기 | 승점 | 득실 |\n|---|---|---|---|---|\n| 1 | Imaginary United | 9 | 24 | +12 |\n\n"


class InputsRecordTest(DataDir):
    def setUp(self):
        super().setUp()
        self.write("fotmob/20261101/team_daily_report_Arsenal_matches.md", "# 📅 Weekly Report: Arsenal\n\n" + MATCH)
        folder = self.root / "newsletter" / "20261102"
        self.write("newsletter/20261102/inputs/Arsenal.json", {
            "version": 1, "team": "Arsenal", "date": "20261102", "shown_separately": ["Bukayo Saka"],
            "news": [{"tag": "N1", "headline": "Arsenal appeal rejected - BBC", "link": "https://www.bbc.co.uk/sport/a1",
                      "published": "2026-10-29 17:19", "collected": "2026-10-29",
                      "summary": "Max Dowman will miss three matches after the appeal is rejected."}]})
        self.file = folder / "newsletter_Arsenal.md"
        self.patch = patch.object(utils, "DATA_ROOT", self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        super().tearDown()

    def evaluate(self, blocks=""):
        self.file.write_text(NEWSLETTER.replace("{blocks}", blocks), encoding="utf-8")
        return evaluate_newsletter(self.file)

    def test_a_fact_only_in_the_summary_is_grounded(self):
        result = self.evaluate()
        self.assertEqual(result["news_grounding"]["score"], 1.0)
        self.assertNotIn("Max Dowman", result["hallucination"].get("hallucinated", []))

    def test_scores_are_the_same_with_and_without_the_code_blocks(self):
        without, with_blocks = self.evaluate(), self.evaluate(BLOCK)
        self.assertEqual(without["components"], with_blocks["components"])

    def test_items_are_rebuilt_from_the_record(self):
        items = utils.news_items_from_inputs(json.loads((self.file.parent / "inputs" / "Arsenal.json").read_text()))
        self.assertEqual(items[0].summary, "Max Dowman will miss three matches after the appeal is rejected.")
        self.assertIn("Max Dowman", items[0].source_text)


if __name__ == "__main__":
    unittest.main()
