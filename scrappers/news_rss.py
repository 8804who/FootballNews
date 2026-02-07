import requests
import feedparser
import os
from datetime import datetime

from config import TEAMS

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
            
            news_items = []
            for entry in feed.entries[:5]:  # 상위 5개만 추출
                news_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published
                })
                
            return news_items

    def get_transfer_news_rss_markdown(self, news_items):
        if not news_items:
            return None
        markdown = "# Transfer Rumors\n"
        for item in news_items:
            markdown += f"- {item['title']} ({item['link']})\n"
        return markdown


news_rss = NewsRSS()