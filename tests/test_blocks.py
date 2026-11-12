"""The code-rendered 순위 / 다음 경기 / 결장 blocks and the FotMob overview
they're built from."""

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from markdown_it import MarkdownIt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import newsletter_sections as sections
from scrappers.fotmob import FotMobCrawler
from summarizers import blocks

UTC = timezone.utc
END = datetime(2026, 11, 2, tzinfo=UTC)  # the Nov 2 edition: Oct 26 – Nov 1


def row(idx, name, pts, gd=0, played=8, scores="10-5", team_id=None, short=None):
    return {"idx": idx, "id": team_id or idx, "name": name, "shortName": short or name, "played": played,
            "pts": pts, "goalConDiff": gd, "scoresStr": scores}


TABLE = [row(1, "Manchester City", 21, 11, short="Man City", scores="20-9"), row(2, "Arsenal", 21, 8, team_id=9825, scores="15-7"),
         row(3, "Brighton & Hove Albion", 16, 16, short="Brighton")] + [row(i, f"Club {i}", 20 - i) for i in range(4, 21)]


def overview(rows=TABLE, injuries=()):
    return {"collected_at": "2026-11-02T05:30:00Z", "team_id": 9825,
            "league": {"league_name": "Premier League", "league_id": 47, "rows": rows}, "injuries": list(injuries)}


def fixture(kickoff, home, away, finished=False, tournament="Premier League", tid=47, **extra):
    opponent = away if home == "Arsenal" else home
    return {"utc_time": kickoff, "home": home, "away": away, "opponent": opponent, "finished": finished,
            "cancelled": False, "tournament": tournament, "tournament_id": tid, **extra}


PLAYED = [fixture(f"2026-{8 + i // 4:02d}-{1 + (i % 4) * 7:02d}T14:00:00.000Z", "Arsenal", f"Club {i + 4}", finished=True)
          for i in range(7)] + [fixture("2026-11-01T16:30:00.000Z", "Liverpool", "Arsenal", finished=True)]
UPCOMING = [fixture("2026-11-04T20:00:00.000Z", "Slavia Prague", "Arsenal", tournament="Champions League", tid=42),
            fixture("2026-11-07T15:00:00.000Z", "Arsenal", "Hull"),
            fixture("2026-11-21T17:30:00.000Z", "Newcastle", "Arsenal")]
FIXTURES = PLAYED + UPCOMING


class TimeLabelTest(unittest.TestCase):
    def test_korean_time_of_day(self):
        self.assertEqual(blocks.kst_label(datetime(2026, 11, 4, 20, tzinfo=UTC)), "11월 5일(목) 새벽 5시")
        self.assertEqual(blocks.kst_label(datetime(2026, 11, 1, 16, 30, tzinfo=UTC)), "11월 2일(월) 새벽 1시 30분")
        self.assertEqual(blocks.kst_label(datetime(2026, 11, 8, 3, tzinfo=UTC)), "11월 8일(일) 낮 12시")
        self.assertEqual(blocks.kst_label(datetime(2026, 11, 8, 11, tzinfo=UTC)), "11월 8일(일) 저녁 8시")

    def test_saturday_three_pm_in_england_is_sunday_zero_hundred_in_korea(self):
        self.assertEqual(blocks.kst_label(datetime(2026, 11, 7, 15, tzinfo=UTC)), "11월 8일(일) 0시")

    def test_unconfirmed_time(self):
        self.assertEqual(blocks.kst_label(datetime(2026, 11, 7, 15, tzinfo=UTC), time_tbd=True), "11월 8일(일) 시간 미정")


class StandingsTest(unittest.TestCase):
    def test_level_on_points_second_place(self):
        lines, reason = blocks.standings(overview(), FIXTURES, END, "Arsenal")
        self.assertEqual(reason, "rendered")
        self.assertEqual(lines[0], "**2위 · 8경기 승점 21**")
        self.assertIn("선두 Man City와 승점은 같지만 골득실에서 밀립니다.", lines)
        self.assertIn("| 2 | **Arsenal** | 8 | 21 | +8 |", lines)

    def test_leader_and_last_place_windows(self):
        top = [row(1, "Arsenal", 24, 9, team_id=9825)] + [row(i, f"Club {i}", 20 - i) for i in range(2, 21)]
        lines, _ = blocks.standings(overview(top), FIXTURES, END, "Arsenal")
        self.assertIn("2위 Club 2보다 승점 6점 앞선 선두입니다.", lines)
        self.assertEqual([l.split("|")[1].strip() for l in lines if l.startswith("| ") and l[2].isdigit()], ["1", "2", "3"])
        bottom = [row(i, f"Club {i}", 40 - i) for i in range(1, 20)] + [row(20, "Arsenal", 2, -15, team_id=9825)]
        lines, _ = blocks.standings(overview(bottom), FIXTURES, END, "Arsenal")
        self.assertEqual([l.split("|")[1].strip() for l in lines if l.startswith("| ") and l[2].isdigit()], ["18", "19", "20"])
        self.assertIn("19위 Club 19보다 승점 19점 뒤져 있습니다.", lines)

    def test_a_table_older_than_the_last_league_match_is_left_out(self):
        stale = [dict(r, played=7) if r["name"] == "Arsenal" else r for r in TABLE]
        lines, reason = blocks.standings(overview(stale), FIXTURES, END, "Arsenal")
        self.assertIsNone(lines)
        self.assertIn("not up to date", reason)

    def test_no_table_before_the_season_starts(self):
        preseason = [dict(r, played=0, pts=0) for r in TABLE]
        self.assertEqual(blocks.standings(overview(preseason), [], END, "Arsenal"), (None, "season not started"))

    def test_without_a_fixture_list_the_table_cant_be_checked(self):
        self.assertIsNone(blocks.standings(overview(), None, END, "Arsenal")[0])


class NextFixturesTest(unittest.TestCase):
    def test_next_two_unplayed_fixtures_from_the_edition_end(self):
        lines = blocks.next_fixtures(FIXTURES, END, "Arsenal")
        self.assertEqual(lines, ["11월 5일(목) 새벽 5시 · Slavia Prague 원정 · Champions League",
                                 "11월 8일(일) 0시 · Hull 홈 · Premier League"])

    def test_a_match_inside_the_edition_week_is_never_next(self):
        # Liverpool away (Nov 1 16:30 UTC) is on this edition's scoreboard, even
        # if FotMob's list hadn't marked it finished yet.
        unfinished = [dict(f, finished=False) for f in PLAYED[-1:]] + UPCOMING
        self.assertNotIn("Liverpool", " ".join(blocks.next_fixtures(unfinished, END, "Arsenal")))

    def test_cancelled_and_undated_fixtures_are_skipped(self):
        fixtures = [dict(UPCOMING[0], cancelled=True), dict(UPCOMING[1], date_tbd=True), UPCOMING[2]]
        self.assertEqual(len(blocks.next_fixtures(fixtures, END, "Arsenal")), 1)


class InjuriesTest(unittest.TestCase):
    def test_return_dates_in_korean_soonest_first(self):
        listed = blocks.injuries(overview(injuries=[
            {"name": "Bukayo Saka", "positions": "RW,CAM", "role": "Attacker", "expected_return": "Mid December 2026"},
            {"name": "William Saliba", "positions": "CB", "role": "Defender", "expected_return": "Late November 2026"},
            {"name": "Riccardo Calafiori", "positions": "LB,CB", "role": "Defender", "expected_return": "Doubtful"},
            {"name": "Gabriel Jesus", "positions": None, "role": "Attacker", "expected_return": "Early January 2027"},
        ]), date(2026, 11, 2))
        self.assertEqual(listed, [
            "Riccardo Calafiori · 왼쪽 풀백 · 출전 불투명",
            "William Saliba · 센터백 · 11월 말 복귀 예상",
            "Bukayo Saka · 오른쪽 윙어 · 12월 중순 복귀 예상",
            "Gabriel Jesus · 공격수 · 2027년 1월 초 복귀 예상",
        ])

    def test_unknown_or_passed_dates_never_show_english(self):
        self.assertEqual(blocks.return_label("Expected back soon-ish", date(2026, 11, 2))[0], "복귀 시점 미정")
        self.assertEqual(blocks.return_label("Unknown", date(2026, 11, 2))[0], "복귀 시점 미정")
        self.assertEqual(blocks.return_label("Early September 2026", date(2026, 11, 2))[0], "복귀 시점 미정")

    def test_relative_returns_seen_in_fotmob(self):
        today = date(2026, 11, 2)
        self.assertEqual(blocks.return_label("Back in training", today)[0], "훈련 복귀")
        self.assertEqual(blocks.return_label("About a week", today)[0], "약 1주 뒤 복귀 예상")
        self.assertEqual(blocks.return_label("A few weeks", today)[0], "몇 주 뒤 복귀 예상")
        self.assertEqual(blocks.return_label("About 2 months", today)[0], "약 2개월 뒤 복귀 예상")
        self.assertEqual(blocks.return_label("Out for season", today)[0], "시즌 아웃")
        self.assertLess(blocks.return_label("About a week", today)[1], blocks.return_label("Mid December 2026", today)[1])

    def test_long_lists_are_capped(self):
        many = [{"name": f"Player {i}", "positions": "CM", "expected_return": "Unknown"} for i in range(9)]
        listed = blocks.injuries(overview(injuries=many), date(2026, 11, 2))
        self.assertEqual(len(listed), blocks.MAX_INJURIES + 1)
        self.assertEqual(listed[-1], "외 3명")


class RenderTest(unittest.TestCase):
    def html(self, markdown):
        return MarkdownIt("commonmark").enable("table").render(markdown)

    def test_hero_line_is_the_only_bold_in_the_first_paragraph(self):
        # .wrap h2 + p strong renders as a 20px headline (DESIGN.md): only the
        # whole "N위 · …" line may be bold there.
        markdown, info = blocks.render(overview(), FIXTURES, END, "Arsenal")
        self.assertEqual(info["standings"], "rendered")
        self.assertIn("<h2>📍 순위 &amp; 다음 경기</h2>\n<p><strong>2위 · 8경기 승점 21</strong></p>", self.html(markdown))

    def test_heading_follows_what_is_there(self):
        stale = [dict(r, played=7) if r["name"] == "Arsenal" else r for r in TABLE]
        markdown, info = blocks.render(overview(stale), FIXTURES, END, "Arsenal")
        self.assertTrue(markdown.startswith(sections.FIXTURES))
        self.assertIn("not up to date", info["standings"])
        markdown, _ = blocks.render(None, [], END, "Arsenal")
        self.assertEqual(markdown, "")

    def test_injuries_block_and_escaping(self):
        markdown, _ = blocks.render(overview(injuries=[{"name": "A_b*c", "positions": "GK", "expected_return": "Doubtful"}]),
                                    FIXTURES, END, "Arsenal")
        self.assertIn(sections.INJURIES, markdown)
        self.assertIn("A\\_b\\*c · 골키퍼 · 출전 불투명", markdown)
        self.assertNotIn("](", markdown)  # no links: every link must be a collected headline


class OverviewExtractionTest(unittest.TestCase):
    def test_league_table_injuries_and_coaches(self):
        data = {
            "details": {"id": 9825},
            "table": [{"data": {"leagueName": "Champions League", "leagueId": 42, "table": {"all": [{"idx": 1, "name": "X"}]}}},
                      {"data": {"leagueName": "Premier League", "leagueId": 47, "table": {"all": [{"idx": 2, "name": "Arsenal", "pts": 21}]}}}],
            "squad": {"squad": [
                {"title": "coach", "members": [{"name": "Coach", "injury": {"expectedReturn": "Unknown"}}]},
                {"title": "defenders", "members": [{"name": "William Saliba", "positionIdsDesc": "CB", "role": {"fallback": "Defender"},
                                                    "injury": {"expectedReturn": "Late November 2026"}},
                                                   {"name": "Fit Player", "injury": None}]},
            ]},
        }
        result = FotMobCrawler().get_overview(data)
        self.assertEqual(result["league"]["league_id"], 47)
        self.assertEqual(result["league"]["rows"][0]["name"], "Arsenal")
        self.assertEqual([p["name"] for p in result["injuries"]], ["William Saliba"])

    def test_the_clubs_own_league_is_picked_outside_england(self):
        data = {
            "details": {"id": 9847, "primaryLeagueId": 53, "primaryLeagueName": "Ligue 1"},
            "table": [{"data": {"leagueName": "Champions League", "leagueId": 42, "table": {"all": [{"idx": 1, "name": "X"}]}}},
                      {"data": {"leagueName": "Ligue 1", "leagueId": 53, "table": {"all": [{"idx": 1, "name": "Paris Saint-Germain"}]}}}],
        }
        result = FotMobCrawler().get_overview(data)
        self.assertEqual(result["league"]["league_name"], "Ligue 1")
        self.assertEqual(result["league"]["rows"][0]["name"], "Paris Saint-Germain")

    def test_home_and_away_come_from_the_team_id_not_its_name(self):
        # FotMob's fixtures say "PSG" while the team page says "Paris Saint-Germain".
        def fixture(home, away):
            return {"status": {"utcTime": "2026-11-08T20:00:00.000Z", "finished": True, "scoreStr": "2 - 1"},
                    "pageUrl": "/m", "opponent": {"name": "Lyon"}, "home": home, "away": away}
        data = {"details": {"id": 9847, "name": "Paris Saint-Germain"},
                "fixtures": {"allFixtures": {"fixtures": [
                    fixture({"id": 9847, "name": "PSG"}, {"id": 9748, "name": "Lyon"}),
                    fixture({"id": 9748, "name": "Lyon"}, {"id": 9847, "name": "PSG"})]}}}
        crawler = FotMobCrawler()
        crawler._analyze_match_details = lambda url: {"competition": "Ligue 1", "stats": {}, "events": []}
        start = datetime(2026, 11, 7, tzinfo=timezone.utc)
        with patch("scrappers.fotmob.time.sleep"):
            matches = crawler.get_team_matches(start, start + timedelta(days=3), data, 9847)
        self.assertEqual([m["venue"] for m in matches], ["Home", "Away"])

    def test_an_unexpected_shape_costs_only_the_blocks(self):
        result = FotMobCrawler().get_overview({"details": {}, "table": "nope", "squad": {"squad": None}})
        self.assertIsNone(result["league"])
        self.assertEqual(result["injuries"], [])


if __name__ == "__main__":
    unittest.main()
