#src/common/rss_parser.py

import feedparser
import requests
from datetime import datetime
from pytz import timezone

class RSSParser:
    def parse(self, url):
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        current_time = datetime.now(timezone('Asia/Seoul'))
        parsed_entries = []
        for entry in feed.entries:
            parsed_entries.append({
                'title': entry.title,
                'content': entry.description,
                'link': entry.link,
                'published': entry.published,
                'parsed_time': current_time
            })
        return parsed_entries