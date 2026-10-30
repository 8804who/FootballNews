import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluate import hallucination, language_compliance, news_grounding, score_accuracy

SCOREBOARD = """## 📊 한눈에 보는 스코어보드
| 경기 | 스코어 | 한 줄 요약 |
|------|--------|----------|
{rows}
"""


def board(*rows):
    return SCOREBOARD.format(rows="\n".join(f"| {r} | 요약입니다 |" for r in rows))


class ScoreAccuracyTest(unittest.TestCase):
    SOURCE = [("Como", "Manchester United", 4, 1)]

    def test_short_club_names_count_as_correct(self):
        # Oct 26: scored 0% because the model wrote "Man United", as FotMob does.
        result = score_accuracy.evaluate(self.SOURCE, board("Como vs Man United | 4-1"))
        self.assertEqual(result["score"], 1.0)

    def test_the_same_result_written_the_other_way_round_is_correct(self):
        result = score_accuracy.evaluate(self.SOURCE, board("Man United vs Como | 1-4"))
        self.assertEqual(result["score"], 1.0)

    def test_wrong_score_and_rows_not_in_the_source(self):
        result = score_accuracy.evaluate(
            self.SOURCE, board("Como vs Man United | 3-1", "Nottm Forest vs Arsenal | 0-1"))
        self.assertEqual(result["score"], 0.0)
        self.assertEqual(len(result["wrong"]), 1)
        self.assertEqual(result["extra_rows"], [("Nottm Forest", "Arsenal", 0, 1)])

    def test_opponent_spelled_differently_still_matches(self):
        result = score_accuracy.evaluate([("Nottm Forest", "Arsenal", 0, 1)],
                                         board("Nottingham Forest vs Arsenal | 0-1"))
        self.assertEqual(result["score"], 1.0)


class HallucinationNamesTest(unittest.TestCase):
    def test_names_followed_by_korean_particles_are_extracted_whole(self):
        names = hallucination.extract_names("Kevin De Bruyne는 미드필더이고 Erling Haaland의 골이 나왔습니다.")
        self.assertEqual(names, {"Kevin De Bruyne", "Erling Haaland"})

    def test_competitions_outlets_and_our_clubs_are_not_people(self):
        names = hallucination.extract_names(
            "Champions League에서 Man Utd가 이겼다고 Sky Sports와 The Athletic이 전했습니다.")
        self.assertEqual(names, set())


class LanguageComplianceTest(unittest.TestCase):
    def test_required_english_names_dont_count_against_korean(self):
        text = ("Man United가 원정에서 Como에 1-4로 패했습니다. Nico Paz가 선제골을 넣었고 "
                "Joshua Zirkzee가 만회골을 넣었습니다. ([Sky Sports](https://news.example/1))")
        self.assertTrue(language_compliance.evaluate(text)["passed"])

    def test_untranslated_english_words_do(self):
        text = "senior players가 Martinez를 지지했고 Belgian international로서 major impact를 냈습니다."
        result = language_compliance.evaluate(text)
        self.assertFalse(result["passed"])
        self.assertLess(result["ratio"], 0.9)


class NewsGroundingTokensTest(unittest.TestCase):
    def test_names_followed_by_particles_are_checked(self):
        words = news_grounding.build_source_words("Jadon Sancho offered deal by Getafe", set())
        result = news_grounding.evaluate("## 🔁 이적 & 뉴스\n- **Sancho가 Getafe로**", words)
        self.assertEqual(result["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
