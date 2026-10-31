from datetime import datetime, timezone, timedelta
import requests
import re
import time

from playwright.sync_api import sync_playwright


class FotMobCrawler:
    def __init__(self):
        self.base_url = "https://www.fotmob.com/api"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://www.fotmob.com/"
        }
        

    def _get_json(self, endpoint, params=None):
        try:
            response = requests.get(f"{self.base_url}/{endpoint}", headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {endpoint}: {e}")
            return None


    def _get_team_data(self, team_id):
        """Collect raw data for the team by intercepting the browser's API request"""
        team_data = None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(30000)

            def handle_response(response):
                nonlocal team_data
                if team_data:
                    return
                if "fotmob.com" not in response.url:
                    return
                try:
                    data = response.json()
                    if isinstance(data, dict) and "fixtures" in data and "details" in data:
                        print(f"Captured team data from: {response.url}")
                        team_data = data
                except Exception:
                    pass

            page.on("response", handle_response)
            page.goto(f"https://www.fotmob.com/teams/{team_id}/overview")
            page.wait_for_timeout(8000)

            # Fallback: extract from Next.js __NEXT_DATA__ embedded in the page
            if not team_data:
                try:
                    next_data = page.evaluate(
                        "() => JSON.parse(document.getElementById('__NEXT_DATA__').textContent)"
                    )
                    page_props = next_data.get("props", {}).get("pageProps", {})
                    if "fixtures" in page_props and "details" in page_props:
                        team_data = page_props
                    elif "team" in page_props:
                        team_data = page_props["team"]
                    if team_data:
                        print("Captured team data from __NEXT_DATA__")
                except Exception as e:
                    print(f"__NEXT_DATA__ extraction failed: {e}")

            browser.close()

        if not team_data:
            print(f"Error fetching teams: could not capture data for team_id={team_id}")
        return team_data


    def get_team_matches(self, start_date, end_date, team_data, team_id):
        """Collect raw data for the team's recent matches"""
        team_name = team_data.get('details', {}).get('name', 'Unknown')
        team_name = self._transform_team_name(team_name)

        matches = []

        all_fixtures = team_data.get('fixtures', {}).get('allFixtures', {}).get('fixtures', [])

        for match in all_fixtures:
            match_time_str = match.get('status', {}).get('utcTime')
            if not match_time_str:
                continue
            
            try:
                match_date = datetime.strptime(match_time_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            except ValueError:
                continue 
            
            if start_date <= match_date <= end_date:
                finished = match.get('status', {}).get('finished')
                
                if not finished:
                    continue
                
                match_url = match.get('pageUrl')
                opponent = match.get('opponent', {}).get('name')
                score = match.get('status', {}).get('scoreStr')

                home_team = match.get('home', {}).get('name')
                away_team = match.get('away', {}).get('name')
                
                details = self._analyze_match_details(match_url)
                
                match_summary = {
                    "utc_date": match_time_str,
                    "local_date_str": match_date.strftime("%Y-%m-%d %H:%M"),
                    "opponent": opponent,
                    "score": score,
                    "home_team": home_team, 
                    "away_team": away_team,
                    "competition": details['competition'],
                    "venue": "Home" if home_team == team_name else "Away",
                    "stats": details['stats'],
                    "events": details['events']
                }
                matches.append(match_summary)
                time.sleep(0.5)

        return matches


    def _get_transfers_data(self, team_id):
        """Fetch raw transfers data by intercepting the browser's API request"""
        transfers_data = None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(30000)

            def handle_response(response):
                nonlocal transfers_data
                if transfers_data:
                    return
                if "fotmob.com" not in response.url:
                    return
                try:
                    data = response.json()
                    if isinstance(data, dict) and "transfers" in data:
                        print(f"Captured transfers data from: {response.url}")
                        transfers_data = data
                    elif isinstance(data, list) and data and "transferDate" in data[0]:
                        print(f"Captured transfers data from: {response.url}")
                        transfers_data = {"transfers": data}
                except Exception:
                    pass

            page.on("response", handle_response)
            page.goto(f"https://www.fotmob.com/teams/{team_id}/transfers")
            page.wait_for_timeout(8000)
            browser.close()

        if not transfers_data:
            print(f"Error fetching transfers: could not capture data for team_id={team_id}")
        return transfers_data

    def get_team_transfers(self, start_date, end_date, team_data, team_id):
        """Collect raw data for the team's recent transfers"""
        print(f"🔄 Collecting data for Team {team_data['details']['name']}... ({start_date.date()} ~ {end_date.date()})")
        transfers = []

        transfers_data = self._get_transfers_data(team_id)
        if transfers_data:
            raw = transfers_data.get('transfers', [])
            t_list = raw if isinstance(raw, list) else []
            for t in t_list:
                if not isinstance(t, dict):
                    continue
                t_date_str = t.get('transferDate')
                if t_date_str:
                    try:
                        t_date = datetime.strptime(t_date_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                        if start_date <= t_date <= end_date:
                            transfers.append({
                                "player": t.get('name'),
                                "type": f"{t.get('fromClub')} -> {t.get('toClub')}",
                                "date": t_date_str
                            })
                    except Exception:
                        pass
        return transfers


    def get_team_data(self, start_date, end_date, team_id):
        """Collect match and transfer data for the team within the given date range"""
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y%m%d').replace(tzinfo=timezone.utc)
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y%m%d').replace(tzinfo=timezone.utc) + timedelta(days=1) - timedelta(seconds=1)

        team_data = self._get_team_data(team_id)
        if not team_data:
            return None

        matches_data = self.get_team_matches(start_date, end_date, team_data, team_id)
        transfers_data = self.get_team_transfers(start_date, end_date, team_data, team_id)

        report_data = {
            "team_name": team_data['details']['name'],
            "period": f"{start_date.date()} ~ {end_date.date()}",
            "matches": matches_data,
            "transfers": transfers_data,
            "fixtures": self.get_fixture_list(team_data),
            "overview": self.get_overview(team_data),
        }
        return report_data


    def get_overview(self, team_data, league_name="Premier League"):
        """League table and injury list for the newsletter's 순위 / 결장 blocks,
        or None. The team page's shape differs between the intercepted API
        response and the __NEXT_DATA__ fallback, so every key is optional and
        a surprise shape only costs the blocks, never the collection."""
        try:
            return {
                "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "team_id": (team_data.get('details') or {}).get('id'),
                "league": self._league_table(team_data, league_name),
                "injuries": self._injuries(team_data),
            }
        except Exception as e:
            print(f"Overview extraction failed: {e}")
            return None


    def _league_table(self, team_data, league_name):
        """{league_name, league_id, rows} for the domestic league, or None.
        team_data['table'] can also hold a Champions League phase table."""
        tables = team_data.get('table') or []
        candidates = []
        for entry in tables if isinstance(tables, list) else []:
            data = (entry or {}).get('data') or {}
            rows = ((data.get('table') or {}).get('all')) if isinstance(data.get('table'), dict) else None
            if rows:
                candidates.append((data, rows))
        if not candidates:
            return None
        data, rows = next(((d, r) for d, r in candidates if d.get('leagueName') == league_name), candidates[0])
        keep = ("idx", "id", "name", "shortName", "played", "wins", "draws", "losses", "scoresStr", "goalConDiff", "pts")
        return {
            "league_name": data.get('leagueName'),
            "league_id": data.get('leagueId'),
            "rows": [{k: row.get(k) for k in keep} for row in rows],
        }


    def _injuries(self, team_data):
        """Injured squad members with FotMob's expected return ("Mid December 2026")."""
        groups = ((team_data.get('squad') or {}).get('squad')) or []
        injured = []
        for group in groups if isinstance(groups, list) else []:
            if (group or {}).get('title') == 'coach':
                continue
            for member in (group or {}).get('members') or []:
                injury = member.get('injury')
                if not injury:
                    continue
                injured.append({
                    "name": member.get('name'),
                    "positions": member.get('positionIdsDesc'),
                    "role": ((member.get('role') or {}).get('fallback')),
                    "expected_return": injury.get('expectedReturn'),
                })
        return injured


    def get_fixture_list(self, team_data):
        """Every fixture on the team page, played or not. evaluate/gate.py
        checks it so a finished match that was never collected can't silently
        drop out of the newsletter."""
        fixtures = []
        for match in team_data.get('fixtures', {}).get('allFixtures', {}).get('fixtures', []):
            status = match.get('status', {})
            fixtures.append({
                "id": match.get('id'),
                "utc_time": status.get('utcTime'),
                "finished": bool(status.get('finished')),
                "cancelled": bool(status.get('cancelled')),
                # Placeholder kickoffs for fixtures not yet scheduled by TV.
                "date_tbd": bool(status.get('matchDateTbd')),
                "time_tbd": bool(status.get('matchTimeTbd')),
                "score": status.get('scoreStr'),
                # "After penalties" / "After extra time"; with a shootout the
                # side scores below include the penalties (1-1, 5-3 → 6 and 4).
                "decided": (status.get('reason') or {}).get('long'),
                "home_total": (match.get('home') or {}).get('score'),
                "away_total": (match.get('away') or {}).get('score'),
                "home": match.get('home', {}).get('name'),
                "away": match.get('away', {}).get('name'),
                "opponent": match.get('opponent', {}).get('name'),
                "tournament": (match.get('tournament') or {}).get('name'),
                "tournament_id": (match.get('tournament') or {}).get('leagueId'),
            })
        return fixtures

    
    def _transform_team_name(self, team_name):
        team_name_dict = {
            "Manchester United": "Man United",
            "Liverpool": "Liverpool",
            "Chelsea": "Chelsea",
            "Arsenal": "Arsenal",
            "Manchester City": "Man City",
            "Tottenham Hotspur": "Tottenham"
        }
        return team_name_dict.get(team_name, team_name)
    

    def _get_competition(self, page):
        try:
            container = page.locator('[class*="MFHeaderLeagueCSS"]')
            span = container.locator("span")

            competition = span.first.inner_text()
            return competition
        except:
            return None


    def _get_possesion(self, page):
        try:
            spans = page.locator('[class*="PossessionSegment"] span')

            home_possesion = spans.nth(0).inner_text()
            away_possesion = spans.nth(1).inner_text()

            return home_possesion, away_possesion
        except:
            return None, None


    def _get_xg_point(self, page):
        try:
            spans = page.locator('[class*="StatValue"] span')

            home_xg = spans.nth(0).inner_text()
            away_xg = spans.nth(1).inner_text()

            return home_xg, away_xg
        except:
            return None, None


    def _get_total_shots(self, page):
        try:
            spans = page.locator('[class*="StatValue"] span')

            home_total_shots = spans.nth(2).inner_text()
            away_total_shots = spans.nth(3).inner_text()

            return home_total_shots, away_total_shots
        except:
            return None, None


    def _analyze_match_details(self, match_url):
        url = "https://www.fotmob.com" + match_url
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(10000)
            page.set_default_navigation_timeout(30000)

            page.goto(url)
            time.sleep(10)

            competition = self._get_competition(page)
            home_possesion, away_possesion = self._get_possesion(page)
            home_xg, away_xg = self._get_xg_point(page)
            home_total_shots, away_total_shots = self._get_total_shots(page)
            events = self._parse_match_events(page)

            browser.close() 

            match_details = {
                "competition": competition,
                "stats": {
                    "possesion": {
                        "home": home_possesion,
                        "away": away_possesion
                    },
                    "xg_point": {
                        "home": home_xg,
                        "away": away_xg
                    },
                    "total_shots": {
                        "home": home_total_shots,
                        "away": away_total_shots
                    }
                },
                "events": events
            }
            return match_details


    def _safe_text(self, locator):
        return locator.first.inner_text().strip() if locator.count() else None


    def _detect_event_type(self, item):
        if item.locator('[class*="SubIn"]').count() > 0:
            return "substitution"
        if item.locator('[class*="GoalIconWrapper"]').count() > 0:
            return "goal"
        if item.locator('svg g[id$="card-icon"]').count() > 0:
            return "card"
        return "unknown"


    def _parse_extract_time(self, item):
        wrapper = item.locator(
            'xpath=ancestor::div[contains(@class,"MatchEventItemWrapper")]'
        )
        regular_time = self._safe_text(wrapper.locator('[class*="EventTimeMain"]'))
        added_time = self._safe_text(wrapper.locator('[class*="EventTimeAdded"]'))

        regular_time = ''.join(re.findall(r'\d+', regular_time))
        if added_time:
            added_time = ''.join(re.findall(r'\d+', added_time))
        return regular_time + '+' + added_time if added_time else regular_time


    def _detect_side(self, item):
        wrapper = item.locator(
            'xpath=ancestor::div[contains(@class,"MatchEventItemWrapper")]'
        )
        time_el = wrapper.locator('[class*="EventTimeWrapper"]').first
        item_el = wrapper.locator('[class*="TwoLineText"]').first

        if not time_el.count() or not item_el.count():
            return None

        try:
            time_x = time_el.bounding_box()["x"]
            item_x = item_el.bounding_box()["x"]

            # 시간 → 이벤트 (왼쪽에 시간)
            if time_x < item_x:
                return "away"
            else:
                return "home"

        except Exception:
            return None


    def _parse_substitution(self, item):
        return {
            "player_in": self._safe_text(item.locator('[class*="SubIn"]')),
            "player_out": self._safe_text(item.locator('[class*="SubOut"]')),
        }

    def _parse_goal(self, item):
        return {
            "scorer": self._safe_text(
                item.locator('[class*="PlayerLinkWrapper"] span')
            ),
            "score": self._safe_text(
                item.locator('[class*="GoalStringCSS"]')
            ),
            "assist": re.sub(r'assist by ', '', item.locator('[class*="SecondaryText"]').last.inner_text().strip()) if item.locator('[class*="SecondaryText"]').count() > 0 else None,
        }

    def _parse_card(self, item):
        player_name = self._safe_text(
            item.locator('[class*="PlayerLinkWrapper"] span')
        )

        if not player_name:
            return {"player": None, "card_type": None}

        shapes = item.locator("svg rect, svg path")

        fills = [
            (shapes.nth(i).get_attribute("fill") or "").lower()
            for i in range(shapes.count())
        ]

        has_yellow = any("yellow" in f for f in fills)
        has_red = any("red" in f for f in fills)

        if has_yellow and has_red:
            return {"player": player_name, "card_type": "Red Card (Second Yellow Card)"}
        if has_yellow:
            return {"player": player_name, "card_type": "Yellow Card"}
        if has_red:
            return {"player": player_name, "card_type": "Red Card"}

        return {"player": None, "card_type": None}

    def _parse_match_events(self, page):
        events = []
        items = page.locator('[class*="MatchEventItemWrapper"] >> [class*="EventItemCSS"]:visible')

        count = items.count()

        for i in range(count):
            item = items.nth(i)
            event_type = self._detect_event_type(item)
            data = {
                "time": self._parse_extract_time(item),
                "type": event_type,
                "side": self._detect_side(item),
            }

            # type-specific parsing
            if event_type == "substitution":
                data.update(self._parse_substitution(item))

            elif event_type == "goal":
                data.update(self._parse_goal(item))

            elif event_type == "card":
                data.update(self._parse_card(item))
            else:
                continue

            events.append(data)
        return events

    def generate_matches_markdown_report(self, matches):
        if not matches:
            return None
        md = ""
        for match in matches:
            md += f"## 🏟️ Match: vs {match['opponent']}\n"
            md += f"- **Competition:** {match['competition']}\n"
            md += f"- **Date:** {match['local_date_str']}\n"
            md += f"- **Venue:** {match['venue']}\n"
            md += f"- **Score:** {match['score']}\n"
            
            if not match['stats']:
                md += "- No match stats recorded.\n"
            else:
                md += "\n**📊 Match Stats:**\n"
                md += f"| Stat | {match['home_team']} | {match['away_team']} |\n"
                md += "|---|:-:|:-:|\n"
                for s in match['stats'].keys():
                    if s == 'possesion':
                        md += f"| Ball Possesion | {match['stats'][s]['home']} | {match['stats'][s]['away']} |\n"
                    elif s == 'xg_point':
                        md += f"| Expected goals (xG) | {match['stats'][s]['home']} | {match['stats'][s]['away']} |\n"
                    elif s == 'total_shots':
                        md += f"| Total Shots | {match['stats'][s]['home']} | {match['stats'][s]['away']} |\n"

            if not match['events']:
                md += "- No match events recorded.\n"
            else:
                md += "\n**⏱️ Match Events:**\n"
                for e in match['events']:
                    md += f"- `{e['time']}'` **{match['home_team'] if e['side'] == 'home' else match['away_team']}**:"
                    if e['type'] == 'substitution':
                        md += f"  - 🔄 Player Substitution: {e['player_out']} -> {e['player_in']}\n"
                    elif e['type'] == 'goal':
                        md += f"  - ⚽ Goal: {e['scorer']} {e['score']} (assist by {e['assist']})\n"
                    elif e['type'] == 'card':
                        md += f"  - {'🟨' if e['card_type'] == 'Yellow Card' else '🟥'} {e['card_type']}: {e['player']}\n"
            md += "---\n"
        return md

    
    def generate_transfers_markdown_report(self, transfers):
        if not transfers:
            return None
        md = "## 🔁 Transfer Updates\n"
        for t in transfers:
            md += f"- **Player:** {t['player']} **Type:** {t['type']} **Date:** {t['date'].split('T')[0]}\n"
        return md


    def generate_markdown_report(self, data, report_type: str):
        """Convert collected data into a clean Markdown format for LLM input"""
        md = f"# 📅 Weekly Report: {data['team_name']}\n"
        md += f"**Period:** {data['period']}\n\n"
        
        md += "---\n\n"

        if report_type == 'matches':
            if not data['matches']:
                return None
            md += self.generate_matches_markdown_report(data['matches'])
        elif report_type == 'transfers':
            if not data['transfers']:
                return None
            md += self.generate_transfers_markdown_report(data['transfers'])
        else:
            return "Invalid report type."
        
        return md


fot_mob_crawler = FotMobCrawler()