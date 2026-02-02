from datetime import datetime, timedelta, timezone
import requests
import json
import time
import os

from config import FOTMOB_TEAMS, TEAMS

class FotMobCrawler:
    def __init__(self):
        self.base_url = "https://www.fotmob.com/api"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://www.fotmob.com/"
        }
        
        self.round_map = {
            "final": "Final",
            "semi-finals": "Semi-Finals",
            "semi-final": "Semi-Finals",
            "quarter-finals": "Quarter-Finals",
            "quarter-final": "Quarter-Finals",
            "round of 16": "Round of 16",
            "round of 32": "Round of 32",
            "knockout round play-offs": "Round of 16 Play-offs",
            "play-offs": "Play-offs",
            "third place play-off": "Third Place Play-off",
            "community shield": "Community Shield"
        }


    def _get_json(self, endpoint, params=None):
        try:
            response = requests.get(f"{self.base_url}/{endpoint}", headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {endpoint}: {e}")
            return None


    def _get_safe_name(self, player_obj):
        """Extract player name safely from inconsistent API responses"""
        if not player_obj:
            return "Unknown"
        
        raw_name = player_obj.get('name')
        if isinstance(raw_name, str):
            return raw_name
            
        if isinstance(raw_name, dict):
            first = raw_name.get('firstName', '')
            last = raw_name.get('lastName', '')
            full_name = f"{first} {last}".strip()
            return full_name if full_name else "Unknown"

        if 'firstName' in player_obj or 'lastName' in player_obj:
            first = player_obj.get('firstName', '')
            last = player_obj.get('lastName', '')
            return f"{first} {last}".strip()

        return "Unknown"


    def _format_round_info(self, round_info):
        """Format round names into proper English"""
        if not round_info:
            return ""
            
        raw = str(round_info).lower().strip()
        
        for key, val in self.round_map.items():
            if key in raw:
                return val
        
        if raw.isdigit():
            return f"Matchweek {raw}"
            
        return str(round_info).capitalize()


    def get_team_data(self, team_id):
        """Collect raw data for the team"""
        team_data = self._get_json("teams", params={"id": team_id})
        if not team_data:
            return None
        return team_data


    def get_team_weekly_matches(self, team_data, team_id):
        """Collect raw data for the team's recent matches"""
        today = datetime.now(timezone.utc)
        start_date = today - timedelta(days=7)
        
        team_name = team_data.get('details', {}).get('name', 'Unknown')

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
            
            if start_date <= match_date <= today:
                match_id = match.get('id')
                opponent = match.get('opponent', {}).get('name')
                score = match.get('status', {}).get('scoreStr')
                
                details = self._analyze_match_details(match_id, team_id)
                
                match_summary = {
                    "utc_date": match_time_str,
                    "local_date_str": match_date.strftime("%Y-%m-%d %H:%M"),
                    "opponent": opponent,
                    "score": score,
                    "home_team": team_name if details['venue'] == "Home" else opponent, 
                    "away_team": opponent if details['venue'] == "Home" else team_name,
                    "competition": details['competition'],
                    "venue": details['venue'],
                    "mom": details['mom'],
                    "stats": details['stats'],
                    "events": details['events']
                }
                matches.append(match_summary)
                time.sleep(0.8) 

        return matches


    def get_team_weekly_transfers(self, team_data, team_id):
        """Collect raw data for the team's recent transfers"""
        today = datetime.now(timezone.utc)
        start_date = today - timedelta(days=7)
        
        print(f"🔄 Collecting data for Team {team_data['details']['name']}... ({start_date.date()} ~ {today.date()})")

        team_name = team_data.get('details', {}).get('name', 'Unknown')
        
        transfers = []

        transfers_data = self._get_json("transfers", params={"id": team_id, "type": "team"})
        if transfers_data:
            t_list = transfers_data if isinstance(transfers_data, list) else transfers_data.get('transfers', [])
            for t in t_list:
                t_date_str = t.get('transferDate')
                if t_date_str:
                    try:
                        t_date = datetime.strptime(t_date_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                        if start_date <= t_date <= today:
                            transfers.append({
                                "player": t.get('name'),
                                "type": f"{t.get('fromClub')} -> {t.get('toClub')}",
                                "date": t_date_str
                            })
                    except:
                        pass
        return transfers


    def get_team_weekly_data(self, team_id):
        """Collect raw data for the team's recent matches"""
        team_data = self.get_team_data(team_id)
        if not team_data:
            return None

        today = datetime.now()
        start_date = today - timedelta(days=7)

        matches_data = self.get_team_weekly_matches(team_data, team_id)
        transfers_data = self.get_team_weekly_transfers(team_data, team_id)

        report_data = {
            "team_name": team_data['details']['name'],
            "period": f"{start_date.date()} ~ {today.date()}",
            "matches": matches_data,
            "transfers": transfers_data
        }
        return report_data

    def _analyze_match_events(self, home_team_name, away_team_name, events):
        result = []
        for event in events:
            evt_type = event.get('type')
            minute = event.get('time')
            is_home_event = event.get('isHome')
            event_team = home_team_name if is_home_event else away_team_name
            
            primary_player_obj = event.get('player')
            primary_player_name = self._get_safe_name(primary_player_obj)
            
            desc = ""
            
            if evt_type == 'Goal':
                kind = event.get('kind')
                goal_prefix = "⚽ Goal"
                if kind == 'own-goal': goal_prefix = "⚽ Own Goal"
                if kind == 'penalty': goal_prefix = "⚽ Penalty Goal"
                
                desc = f"{goal_prefix}: {primary_player_name}"
                
                assist_obj = event.get('assistPlayer')
                if assist_obj:
                    assist_name = self._get_safe_name(assist_obj)
                    if assist_name and assist_name != "Unknown":
                        desc += f" (Assist: {assist_name})"

            elif evt_type == 'Card':
                card_val = event.get('card', '')
                icon = "🟥" if card_val == 'Red' else "🟨"
                desc = f"{icon} {card_val} Card: {primary_player_name}"
            
            else:
                continue

            result.append({
                "time": f"{minute}'",
                "team": event_team,
                "description": desc
            })
        return result


    def _analyze_match_mom(self, player_of_the_match):
        if not player_of_the_match:
            return "N/A"
        mom_name = self._get_safe_name(player_of_the_match)
        mom_rating = player_of_the_match.get('rating', {}).get('num', 'N/A')
        mom_team = player_of_the_match.get('teamName', '')
        return f"{mom_name} ({mom_team}, Rating: {mom_rating})"


    def _analyze_match_competition(self, league, round_raw):
        round_name = self._format_round_info(round_raw)
        return f"{league} - {round_name}"


    def _analyze_match_venue(self, home_team_id, team_id):
        return "Home" if home_team_id == team_id else "Away"


    def _extract_match_stats(self, content_data):
        """
        경기 세부 통계 추출 (로그 기반 구조 확정)
        """
        stats_list = []
        
        stats_wrapper = content_data.get('stats')
        if not stats_wrapper:
            return []

        all_stat_items = []

        periods = stats_wrapper.get('Periods', {})
        all_periods = periods.get('All', {})
        sections = all_periods.get('stats', [])

        for section in sections:
            items = section.get('stats', [])
            all_stat_items.extend(items)

        target_map = {
            "Ball possession":      (["BallPossesion", "possession"], ["Ball possession", "점유율"]),
            "Expected goals (xG)":  (["expected_goals", "expected_goals_team"], ["Expected goals (xG)", "기대 득점 (xG)"]),
            "Total shots":          (["shots_total", "total_shots"], ["Total shots", "슈팅"]),
            "Shots on target":      (["shots_on_target"], ["Shots on target", "유효 슈팅"]),
            "Big chances":          (["big_chance", "big_chances"], ["Big chances", "결정적 기회"]),
            "Passes accurate":      (["passes_accurate"], ["Passes accurate", "패스 성공"]),
            "Fouls committed":      (["fouls"], ["Fouls committed", "파울"]),
            "Corners":              (["corners"], ["Corners", "코너킥"])
        }

        seen_keys = set()

        for item in all_stat_items:
            item_key = item.get('key')
            item_title = item.get('title')
            stat_values = item.get('stats', [])

            if len(stat_values) != 2:
                continue
            
            found_target_title = None
            for target_title, identifiers in target_map.items():
                keys_list, titles_list = identifiers
                
                if item_key and item_key in keys_list:
                    found_target_title = target_title
                    break
                
                if item_title and item_title in titles_list:
                    found_target_title = target_title
                    break
            
            if found_target_title and found_target_title not in seen_keys:
                stats_list.append({
                    "title": found_target_title,
                    "home": stat_values[0],
                    "away": stat_values[1]
                })
                seen_keys.add(found_target_title)
                
        return stats_list
    

    def _analyze_match_details(self, match_id, team_id):
        data = self._get_json("matchDetails", params={"matchId": match_id})
        result = {} # competition, venue, mom, events
        
        if not data:
            return result

        general = data.get('general', {})
        content = data.get('content', {})
        match_facts = content.get('matchFacts', {})

        result['competition'] = self._analyze_match_competition(
            league=general.get('leagueName', ''), 
            round_raw=general.get('matchRound', '')
        )
        result['venue'] = self._analyze_match_venue(
            home_team_id=general.get('homeTeam', {}).get('id'), 
            team_id=team_id
        )
        result['mom'] = self._analyze_match_mom(player_of_the_match=match_facts.get('playerOfTheMatch', {}))
        result['stats'] = self._extract_match_stats(content)
        result['events'] = self._analyze_match_events(home_team_name=general.get('homeTeam', {}).get('name'), 
            away_team_name=general.get('awayTeam', {}).get('name'), 
            events=match_facts.get('events', {}).get('events', [])
        )
        
        return result


    def generate_matches_markdown_report(self, matches):
        md = ""
        for match in matches:
                md += f"## 🏟️ Match: vs {match['opponent']}\n"
                md += f"- **Competition:** {match['competition']}\n"
                md += f"- **Date:** {match['local_date_str']}\n"
                md += f"- **Venue:** {match['venue']}\n"
                md += f"- **Score:** {match['score']}\n"
                md += f"- **Man of the Match:** {match['mom']}\n"
                
                if not match['stats']:
                    md += "- No match stats recorded.\n"
                else:
                    md += "\n**📊 Match Stats:**\n"
                    md += f"| Stat | {match['home_team']} | {match['away_team']} |\n"
                    md += "|---|:-:|:-:|\n"
                    for s in match['stats']:
                        md += f"| {s['title']} | {s['home']} | {s['away']} |\n"

                md += "\n**⏱️ Key Events:**\n"
                if not match['events']:
                    md += "- No major events recorded.\n"
                else:
                    for evt in match['events']:
                        md += f"- `{evt['time']}` **{evt['team']}**: {evt['description']}\n"
                
                md += "\n---\n\n"
        return md

    
    def generate_transfers_markdown_report(self, transfers):
        md = "## 🔁 Transfer Updates\n"
        for t in transfers:
            md += f"- **{t['player']}**: {t['type']} ({t['date'].split('T')[0]})\n"
        return md


    def generate_markdown_report(self, data, report_type: str):
        """Convert collected data into a clean Markdown format for LLM input"""
        if not data:
            return "No data available."

        md = f"# 📅 Weekly Report: {data['team_name']}\n"
        md += f"**Period:** {data['period']}\n\n"
        
        md += "---\n\n"

        if report_type == 'matches':
            md += self.generate_matches_markdown_report(data['matches'])
        elif report_type == 'transfers':
            md += self.generate_transfers_markdown_report(data['transfers'])
        else:
            return "Invalid report type."
        
        return md


fot_mob_crawler = FotMobCrawler()