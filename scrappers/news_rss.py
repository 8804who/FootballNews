import re
from datetime import datetime, timedelta, timezone

import feedparser
import requests

from edition import is_index_page
from team_names import aliases


def _mentions_team(title, team_aliases):
    """Whether a headline names the team, under any of its spellings
    ('Man Utd', 'Spurs' — see teams.yml).

    Google News RSS ranks loosely-relevant results even for a quoted team
    query — other-team-only stories and generic league pages routinely rank
    highly for a "{team} transfer" search. Fetched entries are filtered
    against these aliases so only headlines that actually mention the team
    are kept. Whole words only, so a short alias can't match inside another
    word.
    """
    lowered = title.lower()
    return any(
        re.search(rf"(?<![^\W_]){re.escape(a.lower())}(?![^\W_])", lowered)
        for a in team_aliases
    )


MAX_AGE_DAYS = 7


def _published_at(entry):
    """Publish time in UTC, or None if the feed gave no parseable date."""
    parsed = getattr(entry, "published_parsed", None)
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def _is_recent(published):
    """True if published within MAX_AGE_DAYS (unparseable dates are dropped)."""
    if published is None:
        return False
    return datetime.now(timezone.utc) - published <= timedelta(days=MAX_AGE_DAYS)


class NewsRSS:
    def __init__(self):
        pass

    def get_transfer_news_rss(self, team_name):
            """
            구글 뉴스 RSS를 활용해 공신력 있는 소스의 이적 루머만 추출합니다.
            """
            # 검색어: 팀명 + transfer + (공신력 있는 언론사 필터)
            query = f'"{team_name}" transfer (site:skysports.com OR site:bbc.co.uk OR site:theathletic.com)'
            encoded_query = requests.utils.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-GB&gl=GB&ceid=GB:en"

            feed = feedparser.parse(rss_url)

            team_aliases = aliases(team_name)
            news_items = []
            for entry in feed.entries:
                if not _mentions_team(entry.title, team_aliases):
                    continue  # headline doesn't actually mention this team
                if is_index_page(entry.title, team_aliases):
                    continue  # club landing page, not a story
                published = _published_at(entry)
                if not _is_recent(published):
                    continue  # stale story
                news_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published,
                    "published_at": published,
                })
                if len(news_items) == 5:  # 상위 5개만 추출
                    break

            return news_items

    def get_news_rss_markdown(self, news_items, team_name):
        if not news_items:
            return None
        markdown = f"## Team: {team_name}\n News Rumors:\n"
        for item in news_items:
            # The publish time lets edition.py keep each headline in the right
            # week and drop previews of matches that have since been played.
            markdown += f"- [{item['published_at']:%Y-%m-%d %H:%M}] {item['title']} ({item['link']})\n"
        return markdown


news_rss = NewsRSS()
