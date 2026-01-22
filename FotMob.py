import requests
import json
from datetime import datetime, timedelta
import time
import os

from config import FOTMOB_TEAMS

class FotMobCrawler:
    def __init__(self):
        self.base_url = "https://www.fotmob.com/api"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://www.fotmob.com/"
        }
        
        # Round name formatter (Ensure standard English naming)
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
        
        # 1. Check mapping
        for key, val in self.round_map.items():
            if key in raw:
                return val
        
        # 2. Numeric rounds (e.g., League Matchweek)
        if raw.isdigit():
            return f"Matchweek {raw}"
            
        # 3. Default capitalization
        return str(round_info).capitalize()

    def get_team_weekly_data(self, team_id):
        """Collect raw data for the team's recent matches"""
        today = datetime.now()
        start_date = today - timedelta(days=7)
        
        print(f"🔄 Collecting data for Team ID {team_id}... ({start_date.date()} ~ {today.date()})")

        team_data = self._get_json("teams", params={"id": team_id})
        if not team_data:
            return None

        team_name = team_data.get('details', {}).get('name', 'Unknown')
        
        report_data = {
            "team_name": team_name,
            "period": f"{start_date.date()} ~ {today.date()}",
            "matches": [],
            "transfers": []
        }

        all_fixtures = team_data.get('fixtures', {}).get('allFixtures', {}).get('fixtures', [])
        
        for match in all_fixtures:
            match_time_str = match.get('status', {}).get('utcTime')
            if not match_time_str:
                continue
            
            try:
                match_date = datetime.strptime(match_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            except ValueError:
                continue 
            
            if start_date <= match_date <= today:
                match_id = match.get('id')
                opponent = match.get('opponent', {}).get('name')
                score = match.get('status', {}).get('scoreStr')
                
                print(f"   Analyzing match: vs {opponent} (ID: {match_id})")
                
                details = self._analyze_match_details(match_id, team_id)
                
                match_summary = {
                    "utc_date": match_time_str,
                    "local_date_str": match_date.strftime("%Y-%m-%d %H:%M"),
                    "opponent": opponent,
                    "score": score,
                    "competition": details['competition'],
                    "venue": details['venue'],
                    "mom": details['mom'],
                    "events": details['events']
                }
                report_data['matches'].append(match_summary)
                time.sleep(0.8) 

        # Transfers logic (kept same, but output keys in English context)
        transfers_data = self._get_json("transfers", params={"id": team_id, "type": "team"})
        if transfers_data:
            t_list = transfers_data if isinstance(transfers_data, list) else transfers_data.get('transfers', [])
            for t in t_list:
                t_date_str = t.get('transferDate')
                if t_date_str:
                    try:
                        t_date = datetime.strptime(t_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                        if start_date <= t_date <= today:
                            report_data['transfers'].append({
                                "player": t.get('name'),
                                "type": f"{t.get('fromClub')} -> {t.get('toClub')}",
                                "date": t_date_str
                            })
                    except:
                        pass

        return report_data

    def _analyze_match_details(self, match_id, target_team_id):
        data = self._get_json("matchDetails", params={"matchId": match_id})
        result = {
            "competition": "Unknown",
            "venue": "Unknown",
            "mom": "N/A",
            "events": []
        }
        
        if not data:
            return result

        general = data.get('general', {})
        content = data.get('content', {})
        match_facts = content.get('matchFacts', {})

        # A. Competition & Round
        league = general.get('leagueName', '')
        round_raw = general.get('matchRound', '')
        round_name = self._format_round_info(round_raw)
        result['competition'] = f"{league} - {round_name}"

        # B. Venue
        home_team_id = general.get('homeTeam', {}).get('id')
        result['venue'] = "Home" if home_team_id == target_team_id else "Away"

        # C. MOM
        mom_data = match_facts.get('playerOfTheMatch')
        if mom_data:
            mom_name = self._get_safe_name(mom_data)
            mom_rating = mom_data.get('rating', {}).get('num', 'N/A')
            mom_team = mom_data.get('teamName', '')
            result['mom'] = f"{mom_name} ({mom_team}, Rating: {mom_rating})"
        else:
            result['mom'] = "N/A"

        # D. Events (English)
        home_team_name = general.get('homeTeam', {}).get('name')
        away_team_name = general.get('awayTeam', {}).get('name')
        
        events_raw = match_facts.get('events', {}).get('events', [])
        
        for event in events_raw:
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

            elif evt_type == 'Substitution':
                in_player = primary_player_name 
                swap_list = event.get('swap', [])
                out_player = "Unknown"
                if swap_list and len(swap_list) > 0:
                    out_player_obj = swap_list[0]
                    out_player = self._get_safe_name(out_player_obj)
                desc = f"🔄 Sub: {in_player} (IN) ↔ {out_player} (OUT)"

            elif evt_type == 'Var':
                decision = event.get('kind') or "Check in progress"
                desc = f"📺 VAR: {decision}"
            
            else:
                desc = f"{evt_type}: {primary_player_name}"

            result['events'].append({
                "time": f"{minute}'",
                "team": event_team,
                "description": desc
            })
            
        return result

    def generate_markdown_report(self, data):
        """Convert collected data into a clean Markdown format for LLM input"""
        if not data:
            return "No data available."

        md = f"# 📅 Weekly Report: {data['team_name']}\n"
        md += f"**Period:** {data['period']}\n\n"
        
        md += "---\n\n"

        # Matches Section
        if not data['matches']:
            md += "No matches played in this period.\n\n"
        else:
            for match in data['matches']:
                md += f"## 🏟️ Match: vs {match['opponent']}\n"
                md += f"- **Competition:** {match['competition']}\n"
                md += f"- **Date:** {match['local_date_str']}\n"
                md += f"- **Venue:** {match['venue']}\n"
                md += f"- **Score:** {match['score']}\n"
                md += f"- **Man of the Match:** {match['mom']}\n"
                
                md += "\n**⏱️ Key Events:**\n"
                if not match['events']:
                    md += "- No major events recorded.\n"
                else:
                    for evt in match['events']:
                        md += f"- `{evt['time']}` **{evt['team']}**: {evt['description']}\n"
                
                md += "\n---\n\n"

        # Transfers Section
        if data['transfers']:
            md += "## 🔁 Transfer Updates\n"
            for t in data['transfers']:
                md += f"- **{t['player']}**: {t['type']} ({t['date'].split('T')[0]})\n"
        
        return md

# --- Main Execution ---
if __name__ == "__main__":
    crawler = FotMobCrawler()
    
    for team in FOTMOB_TEAMS:
        target_team_id = team['id']
    
        # 1. Get Data (JSON Structure)
        raw_data = crawler.get_team_weekly_data(target_team_id)
        
        # 2. Convert to Markdown (For LLM / Newsletter)
        markdown_output = crawler.generate_markdown_report(raw_data)
        
        os.makedirs(f"datas/fotmob/{datetime.now().strftime('%Y%m%d')}", exist_ok=True)
        with open(f"datas/fotmob/{datetime.now().strftime('%Y%m%d')}/team_weekly_report_{target_team_id}.md", "w") as f:
            f.write(markdown_output)