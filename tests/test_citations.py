import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from edition import NewsItem
from summarizers.citations import format_news_input, link_citations

ITEMS = [
    NewsItem(headline="Haaland doubt for derby - BBC", link="https://news.example/1",
             published=datetime(2026, 10, 20, 7, tzinfo=timezone.utc), collected=date(2026, 10, 21)),
    NewsItem(headline="City eye winger - Paper Talk - Sky Sports", link="https://news.example/2",
             published=None, collected=date(2026, 10, 22)),
]


class FormatNewsInputTest(unittest.TestCase):
    def test_one_tagged_line_per_headline(self):
        self.assertEqual(format_news_input(ITEMS).splitlines(), [
            "- [N1] 2026-10-20 · BBC · 보도 · Haaland doubt for derby",
            "- [N2] 2026-10-22 · Sky Sports · 가십 · City eye winger - Paper Talk",
        ])


class LinkCitationsTest(unittest.TestCase):
    def test_tag_becomes_a_source_link(self):
        text, unknown = link_citations("- **Haaland 결장 우려** (보도) — 설명입니다. [N1]", ITEMS)
        self.assertEqual(text, "- **Haaland 결장 우려** (보도) — 설명입니다. ([BBC](https://news.example/1))")
        self.assertEqual(unknown, [])

    def test_several_tags_in_either_form_become_one_group(self):
        expected = "설명 ([BBC](https://news.example/1), [Sky Sports](https://news.example/2))"
        self.assertEqual(link_citations("설명 [N1][N2]", ITEMS)[0], expected)
        self.assertEqual(link_citations("설명 [N1, N2]", ITEMS)[0], expected)

    def test_two_stories_from_one_outlet_get_distinct_labels(self):
        same_outlet = ITEMS + [NewsItem(headline="Haaland back in training - BBC", link="https://news.example/3",
                                        published=None, collected=date(2026, 10, 22))]
        text, _ = link_citations("설명 [N1][N3][N1]", same_outlet)
        self.assertEqual(text, "설명 ([BBC](https://news.example/1), [BBC 2](https://news.example/3))")

    def test_unknown_tags_are_removed_and_reported(self):
        text, unknown = link_citations("설명 [N7]", ITEMS)
        self.assertEqual((text, unknown), ("설명", ["N7"]))


if __name__ == "__main__":
    unittest.main()
