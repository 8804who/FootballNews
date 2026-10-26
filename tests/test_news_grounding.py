import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluate import news_grounding

SOURCE = """- Jadon Sancho offered shock deal by Getafe - Paper Talk - Sky Sports
- Riccardo Calafiori adds to Arsenal injury woes - Sky Sports"""

NEWSLETTER = """## 🏆 이번 주 헤드라인
**Arsenal, Bukayo Saka 멀티골**

## 🔁 이적 & 뉴스
### 🧪 루머 밀
- **Jadon Sancho, Getafe 제안 받았습니다** — 가능성은 40%입니다. (Sky Sports)
- **Jordan Placeholder 영입전에서 Demo United와 충돌** — 가능성은 70%입니다. (Sky Sports)
"""


class NewsGroundingTest(unittest.TestCase):
    def test_grounded_and_leaked_items(self):
        words = news_grounding.build_source_words(SOURCE, set())
        result = news_grounding.evaluate(NEWSLETTER, words)
        self.assertEqual(result["score"], 0.5)
        self.assertEqual(len(result["ungrounded"]), 1)
        self.assertIn("Placeholder", result["ungrounded"][0])

    def test_section_only_covers_news_heading(self):
        section = news_grounding.extract_news_section(NEWSLETTER)
        self.assertNotIn("Bukayo Saka", section)
        self.assertIn("Jadon Sancho", section)

    def test_no_news_section_is_unmeasured(self):
        result = news_grounding.evaluate("## 🏆 헤드라인\n본문", {"x"})
        self.assertIsNone(result["score"])


if __name__ == "__main__":
    unittest.main()
