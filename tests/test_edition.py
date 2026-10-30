import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import edition

UTC = timezone.utc


def match_block(opponent, kickoff, venue="Home", score="1 - 0", events="- No match events recorded.\n"):
    return (
        f"## 🏟️ Match: vs {opponent}\n"
        "- **Competition:** Premier League\n"
        f"- **Date:** {kickoff}\n"
        f"- **Venue:** {venue}\n"
        f"- **Score:** {score}\n"
        f"{events}"
        "---\n"
    )


def matches_file(*blocks):
    return "# 📅 Weekly Report: Arsenal\n**Period:** 2026-10-18 ~ 2026-10-19\n\n---\n\n" + "".join(blocks)


def news_file(*lines):
    return "## Team: Manchester City\n News Rumors:\n" + "".join(f"{line}\n" for line in lines)


class DataDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, kind, day, name, text):
        path = self.root / kind / day / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


class EditionWindowTest(unittest.TestCase):
    def test_monday_run_covers_last_monday_through_sunday(self):
        start, end = edition.edition_window(datetime(2026, 10, 26, 5, 30, tzinfo=UTC))
        self.assertEqual(start, datetime(2026, 10, 19, tzinfo=UTC))
        self.assertEqual(end, datetime(2026, 10, 26, tzinfo=UTC))
        self.assertEqual(edition.date_range_label(start, end), "2026-10-19 ~ 2026-10-25")

    def test_rerun_later_in_the_week_gets_the_same_window(self):
        self.assertEqual(edition.edition_window(datetime(2026, 10, 27, 9, tzinfo=UTC)),
                         edition.edition_window(datetime(2026, 10, 26, 1, tzinfo=UTC)))

    def test_consecutive_editions_neither_overlap_nor_leave_a_gap(self):
        _, previous_end = edition.edition_window(datetime(2026, 10, 19, tzinfo=UTC))
        start, _ = edition.edition_window(datetime(2026, 10, 26, tzinfo=UTC))
        self.assertEqual(previous_end, start)

    def test_folders_run_from_the_week_start_through_the_run_day(self):
        start, _ = edition.edition_window(datetime(2026, 10, 26, tzinfo=UTC))
        dates = edition.folder_dates(start, datetime(2026, 10, 26, 6, tzinfo=UTC))
        self.assertEqual((dates[0], dates[-1], len(dates)), ("20261019", "20261026", 8))


class LoadMatchesTest(DataDirTestCase):
    RUN = datetime(2026, 10, 26, 5, tzinfo=UTC)

    def load(self, run=RUN):
        start, end = edition.edition_window(run)
        return edition.load_matches("Arsenal", start, end, run, root=self.root)

    def test_last_weeks_sunday_is_not_repeated(self):
        # Oct 2026: the Oct 19 folder held Sunday Oct 18's match, which the
        # Oct 19 edition covered — and the Oct 26 edition showed it again.
        self.write("fotmob", "20261019", "team_daily_report_Arsenal_matches.md",
                   matches_file(match_block("Nottm Forest", "2026-10-18 14:00", "Away", "0 - 1")))
        self.write("fotmob", "20261022", "team_daily_report_Arsenal_matches.md",
                   matches_file(match_block("Bayern München", "2026-10-21 19:00", "Away", "2 - 2")))
        self.assertEqual([edition.match_opponent(b) for b in self.load()], ["Bayern München"])

    def test_a_match_collected_on_several_days_appears_once(self):
        block = match_block("Bayern München", "2026-10-21 19:00", "Away", "2 - 2")
        for day in ("20261022", "20261023", "20261024"):
            self.write("fotmob", day, "team_daily_report_Arsenal_matches.md", matches_file(block))
        self.assertEqual(len(self.load()), 1)

    def test_a_match_missed_by_failed_runs_is_found_in_a_later_folder(self):
        # The Oct 25 and Oct 26 runs failed; a Tuesday run looks 3 days back.
        self.write("fotmob", "20261027", "team_daily_report_Arsenal_matches.md",
                   matches_file(match_block("Burnley", "2026-10-24 14:00")))
        blocks = self.load(datetime(2026, 10, 27, 9, tzinfo=UTC))
        self.assertEqual([edition.match_opponent(b) for b in blocks], ["Burnley"])

    def test_the_latest_copy_of_a_match_wins(self):
        partial = match_block("Como", "2026-10-21 16:45", "Away", "4 - 1", events="- partial\n")
        final = match_block("Como", "2026-10-21 16:45", "Away", "4 - 1", events="- final\n")
        self.write("fotmob", "20261022", "team_daily_report_Arsenal_matches.md", matches_file(partial))
        self.write("fotmob", "20261023", "team_daily_report_Arsenal_matches.md", matches_file(final))
        self.assertIn("- final", self.load()[0])

    def test_matches_markdown_puts_all_blocks_under_one_header(self):
        blocks = [match_block("Como", "2026-10-21 16:45"), match_block("Leeds", "2026-10-25 14:00")]
        start, end = edition.edition_window(self.RUN)
        text = edition.matches_markdown("Arsenal", blocks, start, end)
        self.assertEqual(text.count("Weekly Report: Arsenal"), 1)
        self.assertEqual(text.count("Match: vs"), 2)
        self.assertEqual(edition.matches_markdown("Arsenal", [], start, end), "")


class LoadNewsTest(DataDirTestCase):
    RUN = datetime(2026, 10, 26, 5, tzinfo=UTC)

    def load(self, played=()):
        start, end = edition.edition_window(self.RUN)
        items = edition.load_news("Manchester_City", "Manchester City", start, end, self.RUN, played, root=self.root)
        return [item.title for item in items]

    def test_keeps_headlines_published_this_week_once(self):
        story = "- [2026-10-20 07:00] Man City eye Serie A winger - Sky Sports (https://news.example/1)"
        self.write("news_rss", "20261020", "team_daily_report_Manchester_City.md", news_file(story))
        self.write("news_rss", "20261021", "team_daily_report_Manchester_City.md", news_file(story))
        self.write("news_rss", "20261019", "team_daily_report_Manchester_City.md", news_file(
            "- [2026-10-18 09:00] Man City story from last week - BBC (https://news.example/2)"))
        self.assertEqual(self.load(), ["Man City eye Serie A winger"])

    def test_lines_without_publish_time_fall_back_to_folder_date(self):
        # Files written before collect_news stored publish times.
        self.write("news_rss", "20261019", "team_daily_report_Manchester_City.md",
                   news_file("- Man City old-format last week - BBC (https://news.example/3)"))
        self.write("news_rss", "20261023", "team_daily_report_Manchester_City.md",
                   news_file("- Man City old-format this week - BBC (https://news.example/4)"))
        self.assertEqual(self.load(), ["Man City old-format this week"])

    def test_drops_club_landing_pages(self):
        self.write("news_rss", "20261021", "team_daily_report_Manchester_City.md", news_file(
            "- [2026-10-20 07:00] Man City - Transfer news, results, fixtures, video and audio - BBC (https://news.example/5)",
            "- [2026-10-20 08:00] Manchester City - BBC (https://news.example/6)",
            "- [2026-10-20 09:00] Man City transfer news, rumours and gossip: Live updates - Sky Sports (https://news.example/7)",
            "- [2026-10-20 09:30] Man City vs AEK Athens LIVE! Champions League score updates, news and line-ups - Sky Sports (https://news.example/12)",
            "- [2026-10-20 10:00] Man City confirm Rodri injury - BBC (https://news.example/8)",
        ))
        self.assertEqual(self.load(), ["Man City confirm Rodri injury"])

    def test_drops_previews_of_matches_already_played(self):
        # Oct 26 edition: "Haaland doubt … against AEK Athens" sat next to the
        # 5-1 result of that very match.
        self.write("news_rss", "20261021", "team_daily_report_Manchester_City.md", news_file(
            "- [2026-10-20 07:00] Erling Haaland doubt: Who could play for Man City against AEK Athens? - BBC (https://news.example/9)",
            "- [2026-10-20 22:00] Man City 5-1 AEK Athens: Foden stars - BBC (https://news.example/10)",
        ))
        played = [(datetime(2026, 10, 20, 19, 0, tzinfo=UTC), "AEK Athens")]
        self.assertEqual(self.load(played), ["Man City 5-1 AEK Athens: Foden stars"])

    def test_outlet_and_kind_come_from_the_headline(self):
        item = edition.parse_news_line(
            "- [2026-10-20 07:00] Man City eye winger - Paper Talk - Sky Sports (https://news.example/11)",
            datetime(2026, 10, 21).date())
        self.assertEqual((item.title, item.outlet, item.kind), ("Man City eye winger - Paper Talk", "Sky Sports", "가십"))


class LoadTransfersTest(DataDirTestCase):
    def test_transfers_in_the_week_once(self):
        transfers = (
            "## 🔁 Transfer Updates\n"
            "- **Player:** Alex Sample **Type:** A -> B **Date:** 2026-10-20\n"
            "- **Player:** Old Move **Type:** A -> B **Date:** 2026-10-10\n"
        )
        self.write("fotmob", "20261021", "team_daily_report_Arsenal_transfers.md", transfers)
        self.write("fotmob", "20261022", "team_daily_report_Arsenal_transfers.md", transfers)
        run = datetime(2026, 10, 26, tzinfo=UTC)
        start, end = edition.edition_window(run)
        lines = edition.load_transfers("Arsenal", start, end, run, root=self.root)
        self.assertEqual(len(lines), 1)
        self.assertIn("Alex Sample", lines[0])


if __name__ == "__main__":
    unittest.main()
