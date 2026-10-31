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

BBC_FEED = "https://feeds.bbci.co.uk/sport/football/teams/{slug}/rss.xml"
BBC_PER_RUN = 6
# Live pages, clips and podcasts have no story to summarise.
_BBC_SKIP_PATHS = ("/live/", "/videos/", "/sounds/", "/av/", "/podcasts/")
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_summary(text):
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", text or "")).strip()


def _first_sentence(text):
    return re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]


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

    def get_bbc_team_news(self, team_name, slug):
        """Up to BBC_PER_RUN recent stories from BBC Sport's club feed, each
        with its one-line summary, or None if the feed couldn't be read.

        The club feed also carries stories that only mention the club in
        passing, so an item is kept when the club is named in its title or
        in the first sentence of its summary.
        """
        try:
            response = requests.get(BBC_FEED.format(slug=slug), timeout=15,
                                    headers={"User-Agent": "Mozilla/5.0 FootballNews"})
            response.raise_for_status()
            feed = feedparser.parse(response.content)
        except Exception as e:
            print(f"[{team_name}] ⚠ bbc: feed fetch failed: {e}")
            return None
        if getattr(feed, "bozo", False) and not feed.entries:
            print(f"[{team_name}] ⚠ bbc: feed could not be parsed")
            return None

        team_aliases = aliases(team_name)
        items = []
        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").split("?")[0]
            summary = _clean_summary(entry.get("summary"))
            if not title or not link or any(p in link for p in _BBC_SKIP_PATHS):
                continue
            if not (_mentions_team(title, team_aliases) or _mentions_team(_first_sentence(summary), team_aliases)):
                continue
            if is_index_page(title, team_aliases):
                continue
            published = _published_at(entry)
            if not _is_recent(published):
                continue
            items.append({"title": title, "link": link, "published": f"{published:%Y-%m-%d %H:%M}", "summary": summary})
            if len(items) == BBC_PER_RUN:
                break
        if not items:
            print(f"[{team_name}] ⚠ bbc: no stories about the club in its feed")
        return items

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
