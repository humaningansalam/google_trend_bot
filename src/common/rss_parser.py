from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import feedparser
import requests

SEOUL_TIME_ZONE = ZoneInfo("Asia/Seoul")
RSS_REQUEST_TIMEOUT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class TrendEntry:
    title: str
    content: str
    link: str
    published: str
    observed_at: datetime


class RSSParser:
    def parse(self, url: str) -> list[TrendEntry]:
        response = requests.get(url, timeout=RSS_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()

        feed = feedparser.parse(response.content)
        if not feed.version:
            raise ValueError("RSS response is not a recognized feed")
        if feed.bozo:
            raise ValueError("RSS response is malformed") from feed.bozo_exception

        observed_at = datetime.now(SEOUL_TIME_ZONE)
        return [
            TrendEntry(
                title=_required_text(entry, "title"),
                content=_required_text(entry, "description"),
                link=_required_text(entry, "link"),
                published=_required_text(entry, "published"),
                observed_at=observed_at,
            )
            for entry in feed.entries
        ]


def _required_text(entry: Mapping[str, object], field_name: str) -> str:
    value = entry.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"RSS entry is missing required field: {field_name}")
    return value.strip()
