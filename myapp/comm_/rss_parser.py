import feedparser
from datetime import datetime
from pytz import timezone

class RSSParser:
    def parse(self, url):
        feed = feedparser.parse(url)
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