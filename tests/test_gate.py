import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluate import gate

UTC = timezone.utc
RUN = datetime(2026, 10, 26, tzinfo=UTC)

EDITION = """# Arsenal · 주간 뉴스레터 (2026-10-19 ~ 2026-10-25)

## 🏆 이번 주 헤드라인
**Rice의 극장 동점골**

## ⭐ 이번 주 베스트 경기
Arsenal이 원정에서 Bayern München과 2-2로 비겼습니다. Declan Rice가 동점골을 넣었습니다.

## 📊 한눈에 보는 스코어보드
| 경기 | 스코어 | 한 줄 요약 |
|------|--------|----------|
| Bayern München vs Arsenal | 2-2 | Rice가 해결했습니다 |

## 🔁 이적 & 뉴스
### 🧪 루머 밀
- **Arsenal, 윙어 영입 검토** (보도) — 측면 보강이 필요한 시점입니다. ([BBC](https://news.example/1))
"""


def sources(matches=(), words=(), links=(), fixtures=None):
    return {
        "start": datetime(2026, 10, 19, tzinfo=UTC), "end": RUN,
        "blocks": [], "matches": list(matches), "text": "",
        "words": set(words), "links": set(links), "fixtures": fixtures,
    }


ARSENAL = sources(
    matches=[("Bayern München", "Arsenal", 2, 2)],
    words={"declan", "rice", "bayern", "münchen", "arsenal"},
    links={"https://news.example/1"},
)


class CheckEditionTest(unittest.TestCase):
    def check(self, text=EDITION, own=ARSENAL, others=None):
        return gate.check_edition("Arsenal", RUN, text, {"Arsenal": own, **(others or {})})

    def assertHeldFor(self, result, fragment):
        self.assertTrue(result["hold"])
        self.assertTrue(any(fragment in p for p in result["problems"]), result["problems"])

    def test_a_correct_edition_passes(self):
        result = self.check()
        self.assertFalse(result["hold"], result["problems"])

    def test_a_wrong_score_holds(self):
        self.assertHeldFor(self.check(EDITION.replace("| 2-2 |", "| 2-1 |")), "wrong score")

    def test_last_weeks_match_shown_again_holds(self):
        repeat = EDITION.replace("| Rice가 해결했습니다 |", "| Rice가 해결했습니다 |\n| Nottm Forest vs Arsenal | 0-1 | 결승골 |")
        self.assertHeldFor(self.check(repeat), "not in this week's source")

    def test_a_match_missing_from_the_scoreboard_holds(self):
        own = dict(ARSENAL, matches=ARSENAL["matches"] + [("Arsenal", "Burnley", 2, 0)])
        self.assertHeldFor(self.check(own=own), "missing from the scoreboard")

    def test_a_finished_fixture_that_was_never_collected_holds(self):
        # Oct 26: the weekend's collection failed and the edition went out anyway.
        own = dict(ARSENAL, fixtures=[{
            "utc_time": "2026-10-25T14:00:00.000Z", "finished": True, "cancelled": False,
            "score": "2 - 1", "home": "Arsenal", "away": "Burnley", "tournament": "Premier League",
        }])
        self.assertHeldFor(self.check(own=own), "never collected")

    def test_names_from_the_few_shot_examples_hold(self):
        leak = EDITION + "- **Jordan Placeholder 영입전** (보도) — 설명입니다. ([BBC](https://news.example/1))\n"
        self.assertHeldFor(self.check(leak), "few-shot")

    def test_a_name_only_in_another_clubs_sources_holds(self):
        # Oct 19: Man City rumors (Elliot Anderson, Pep Guardiola) in Arsenal's edition.
        leak = EDITION + "- **Elliot Anderson 영입 경쟁** (보도) — 설명입니다. ([BBC](https://news.example/1))\n"
        city = sources(words={"elliot", "anderson"})
        self.assertHeldFor(self.check(leak, others={"Manchester_City": city}), "only in Manchester City's")

    def test_a_link_to_a_headline_this_club_never_had_holds(self):
        self.assertHeldFor(self.check(EDITION.replace("news.example/1", "news.example/99")), "source link")

    def test_names_in_no_source_only_warn(self):
        result = self.check(EDITION.replace("측면 보강이", "Mikel Arteta 감독의 측면 보강이"))
        self.assertFalse(result["hold"], result["problems"])
        self.assertTrue(any("Mikel Arteta" in w for w in result["warnings"]))


class ExampleNamesTest(unittest.TestCase):
    def test_example_yml_names_are_the_fictional_ones(self):
        names = gate.example_names()
        self.assertIn("Jordan Placeholder", names)
        self.assertIn("Demo United", names)
        self.assertNotIn("Sky Sports", names)


if __name__ == "__main__":
    unittest.main()
