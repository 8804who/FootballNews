import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrappers.news_rss import NewsRSS


def _entry(title, published_parsed=None):
    return SimpleNamespace(
        title=title,
        link=f"https://example.com/{title}",
        published="2026-08-07",
        published_parsed=published_parsed or time.gmtime(),
    )


class TestGetTransferNewsRss(unittest.TestCase):
    def setUp(self):
        self.news_rss = NewsRSS()
        # A mixed feed: two items genuinely about Tottenham, one about a
        # different team only, one generic team-agnostic page — mirrors
        # datas/news_rss/20260515/team_daily_report_Tottenham_Hotspur.md.
        self.entries = [
            _entry("Tottenham Hotspur FC - Transfer news, results, fixtures"),
            _entry("Man Utd transfer news, rumours and gossip: Live updates"),
            _entry("Virgil van Dijk: Liverpool captain ready to leave club"),
            _entry("Spurs eye move for Serie A winger - Sky Sports"),
            _entry("Football Games, Results, Scores, Transfers, News - Sky Sports"),
        ]

    def test_filters_out_other_team_and_generic_entries(self):
        feed = SimpleNamespace(entries=self.entries)
        with patch("scrappers.news_rss.feedparser.parse", return_value=feed):
            items = self.news_rss.get_transfer_news_rss("Tottenham Hotspur")

        titles = [item["title"] for item in items]
        self.assertIn("Tottenham Hotspur FC - Transfer news, results, fixtures", titles)
        self.assertIn("Spurs eye move for Serie A winger - Sky Sports", titles)
        self.assertNotIn("Man Utd transfer news, rumours and gossip: Live updates", titles)
        self.assertNotIn("Virgil van Dijk: Liverpool captain ready to leave club", titles)
        self.assertNotIn("Football Games, Results, Scores, Transfers, News - Sky Sports", titles)

    def test_caps_at_five_after_filtering_not_before(self):
        relevant = [_entry(f"Man City transfer update #{i}") for i in range(7)]
        feed = SimpleNamespace(entries=[_entry("Irrelevant filler")] + relevant)
        with patch("scrappers.news_rss.feedparser.parse", return_value=feed):
            items = self.news_rss.get_transfer_news_rss("Manchester City")

        self.assertEqual(len(items), 5)
        self.assertTrue(all("Man City" in item["title"] for item in items))

    def test_drops_stale_entries(self):
        old = time.gmtime(time.time() - 30 * 86400)
        feed = SimpleNamespace(entries=[
            _entry("Man City old story", published_parsed=old),
            _entry("Man City fresh story"),
        ])
        with patch("scrappers.news_rss.feedparser.parse", return_value=feed):
            items = self.news_rss.get_transfer_news_rss("Manchester City")

        self.assertEqual([i["title"] for i in items], ["Man City fresh story"])


if __name__ == "__main__":
    unittest.main()
