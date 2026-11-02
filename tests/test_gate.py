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

    def assertFlaggedFor(self, result, fragment):
        self.assertTrue(result["flagged"])
        self.assertTrue(any(fragment in p for p in result["problems"]), result["problems"])

    def test_a_correct_edition_passes(self):
        result = self.check()
        self.assertFalse(result["flagged"], result["problems"])

    def test_a_wrong_score_is_flagged(self):
        self.assertFlaggedFor(self.check(EDITION.replace("| 2-2 |", "| 2-1 |")), "wrong score")

    def test_last_weeks_match_shown_again_is_flagged(self):
        repeat = EDITION.replace("| Rice가 해결했습니다 |", "| Rice가 해결했습니다 |\n| Nottm Forest vs Arsenal | 0-1 | 결승골 |")
        self.assertFlaggedFor(self.check(repeat), "not in this week's source")

    def test_a_match_missing_from_the_scoreboard_is_flagged(self):
        own = dict(ARSENAL, matches=ARSENAL["matches"] + [("Arsenal", "Burnley", 2, 0)])
        self.assertFlaggedFor(self.check(own=own), "missing from the scoreboard")

    def test_a_finished_fixture_that_was_never_collected_is_flagged(self):
        # Oct 26: the weekend's collection failed and the edition went out anyway.
        own = dict(ARSENAL, fixtures=[{
            "utc_time": "2026-10-25T14:00:00.000Z", "finished": True, "cancelled": False,
            "score": "2 - 1", "home": "Arsenal", "away": "Burnley", "tournament": "Premier League",
        }])
        self.assertFlaggedFor(self.check(own=own), "never collected")

    def test_names_from_the_few_shot_examples_are_flagged(self):
        leak = EDITION + "- **Jordan Placeholder 영입전** (보도) — 설명입니다. ([BBC](https://news.example/1))\n"
        self.assertFlaggedFor(self.check(leak), "few-shot")

    def test_a_name_only_in_another_clubs_sources_is_flagged(self):
        # Oct 19: Man City rumors (Elliot Anderson, Pep Guardiola) in Arsenal's edition.
        leak = EDITION + "- **Elliot Anderson 영입 경쟁** (보도) — 설명입니다. ([BBC](https://news.example/1))\n"
        city = sources(words={"elliot", "anderson"})
        self.assertFlaggedFor(self.check(leak, others={"Manchester_City": city}), "only in Manchester City's")

    def test_a_link_to_a_headline_this_club_never_had_is_flagged(self):
        self.assertFlaggedFor(self.check(EDITION.replace("news.example/1", "news.example/99")), "source link")

    def test_names_in_no_source_only_warn(self):
        result = self.check(EDITION.replace("측면 보강이", "Mikel Arteta 감독의 측면 보강이"))
        self.assertFalse(result["flagged"], result["problems"])
        self.assertTrue(any("Mikel Arteta" in w for w in result["warnings"]))


class NewChecksTest(unittest.TestCase):
    """Report-only warnings added with the 2026-11 news sections."""

    def check(self, text, own):
        return gate.check_edition("Arsenal", RUN, text, {"Arsenal": own})

    def test_a_confirmed_item_cited_from_gossip_warns(self):
        from edition import NewsItem
        rumor = NewsItem("Arsenal eye move for winger - Paper Talk", "https://news.example/2", None, RUN.date())
        own = dict(ARSENAL, links=ARSENAL["links"] | {rumor.link}, items={rumor.link: rumor})
        text = EDITION + "### ✅ 확정 소식\n- **Arsenal, 윙어 영입 확정** (보도)  \n  계약을 마쳤습니다. ([Sky](https://news.example/2))\n"
        warnings = self.check(text, own)["warnings"]
        self.assertTrue(any("확정 item cites a rumor" in w for w in warnings), warnings)

    def test_an_unlinked_confirmed_item_warns_unless_it_is_fotmobs_own(self):
        text = EDITION + "### ✅ 확정 소식\n- **A 이적 확정** (FotMob 공식)  \n  떠납니다.\n- **B 계약** (보도)  \n  했습니다.\n"
        # B only: A is FotMob's own transfer list, which has no link to give.
        self.assertIn("1 news item(s) without a source link", self.check(text, ARSENAL)["warnings"])

    def test_a_comeback_with_no_lead_change_warns(self):
        never_behind = ("## 🏟️ Match: vs Bayern München\n- **Date:** 2026-10-21 19:00\n- **Venue:** Away\n- **Score:** 1 - 2\n"
                        "- `10'` **Arsenal**:  - ⚽ Goal: A (0 - 1)\n- `50'` **Bayern München**:  - ⚽ Goal: B (1 - 1)\n"
                        "- `80'` **Arsenal**:  - ⚽ Goal: C (1 - 2)\n---\n")
        own = dict(ARSENAL, blocks=[never_behind])
        claim = EDITION.replace("2-2로 비겼습니다.", "2-2로 비겼습니다. 후반에 경기를 뒤집었습니다.")
        self.assertIn("says 역전/뒤집 but no match this week changed leader", self.check(claim, own)["warnings"])
        attempt = EDITION.replace("2-2로 비겼습니다.", "2-2로 비겼습니다. 끝까지 뒤집으려 했습니다.")
        self.assertNotIn("says 역전/뒤집 but no match this week changed leader", self.check(attempt, own)["warnings"])

    def test_the_code_rendered_blocks_are_not_checked(self):
        block = "## 📍 현재 순위\n\n**2위 · 8경기 승점 21**\n\n| 1 | Invented Club FC | 8 | 21 | +11 |\n\n"
        text = EDITION.replace("## 🔁 이적 & 뉴스", block + "## 🔁 이적 & 뉴스")
        self.assertEqual(self.check(text, ARSENAL), self.check(EDITION, ARSENAL))


class ExampleNamesTest(unittest.TestCase):
    def test_example_yml_names_are_the_fictional_ones(self):
        names = gate.example_names()
        self.assertIn("Jordan Placeholder", names)
        self.assertIn("Demo United", names)
        self.assertNotIn("Sky Sports", names)


if __name__ == "__main__":
    unittest.main()
