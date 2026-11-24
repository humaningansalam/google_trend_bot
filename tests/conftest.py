from datetime import datetime
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import pytest

from src.bot.scraper import GoogleTrendsScraper
from src.bot.trend_alert_bot import TrendAlertBot
from src.common.rss_parser import TrendEntry
from src.common.scrape_contracts import ScrapeResult
from src.main import create_app

SEOUL_TIME_ZONE = ZoneInfo("Asia/Seoul")


@pytest.fixture
def trend_entry() -> TrendEntry:
    return TrendEntry(
        title="Test Trend",
        content="Test Content",
        link="https://example.test/trend",
        published="2026-11-24T09:00:00+09:00",
        observed_at=datetime(2026, 11, 24, 9, 0, tzinfo=SEOUL_TIME_ZONE),
    )


@pytest.fixture
def mock_trend_feed(trend_entry: TrendEntry) -> Mock:
    trend_feed = Mock()
    trend_feed.parse.return_value = [trend_entry]
    return trend_feed


@pytest.fixture
def mock_alert_sender() -> Mock:
    return Mock()


@pytest.fixture
def trend_bot(mock_trend_feed: Mock, mock_alert_sender: Mock) -> TrendAlertBot:
    return TrendAlertBot(
        mock_trend_feed,
        poll_interval_minutes=10,
        stop_timeout_seconds=0.1,
        scheduler_check_interval_seconds=0.01,
        alert_sender=mock_alert_sender,
    )


@pytest.fixture
def trend_scraper() -> GoogleTrendsScraper:
    scraper = GoogleTrendsScraper()
    scraper.scrape_trends = AsyncMock(
        return_value=ScrapeResult.success([{"trend": "Test Trend"}])
    )
    return scraper


@pytest.fixture
def app(
    trend_bot: TrendAlertBot,
    trend_scraper: GoogleTrendsScraper,
):
    flask_app = create_app(
        trend_alert_bot=trend_bot,
        trend_scraper=trend_scraper,
    )
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def stop_worker_after_test(trend_bot: TrendAlertBot):
    yield
    if trend_bot.is_active():
        trend_bot.stop()
