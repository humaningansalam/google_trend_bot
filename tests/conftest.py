from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.bot.rss_bot import RSSBot
from src.bot.scraper import Scraper
from src.common.scrape_contracts import ScrapeResult
from src.main import create_app


@pytest.fixture
def mock_rss_parser():
    parser = Mock()
    parser.parse.return_value = [
        {
            "title": "Test Trend",
            "content": "Test Content",
            "link": "http://test.com",
            "published": "2024-01-01",
            "parsed_time": datetime(2024, 1, 1, 0, 0, 0),
        }
    ]
    return parser


@pytest.fixture
def mock_send_alert():
    return Mock()


@pytest.fixture
def test_bot(mock_rss_parser, mock_send_alert):
    return RSSBot(
        rss_parser=mock_rss_parser,
        interval=10,
        stop_timeout=0.1,
        sleep_interval=0.01,
        alert_sender=mock_send_alert,
    )


@pytest.fixture
def test_scraper():
    scraper = Scraper()
    scraper.scrape_trends = AsyncMock(
        return_value=ScrapeResult.success([{"trend": "Test Trend"}])
    )
    return scraper


@pytest.fixture
def app(test_bot, test_scraper):
    app = create_app(bot=test_bot, scraper=test_scraper)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(scope="function", autouse=True)
def cleanup_bot(test_bot):
    yield
    if test_bot.is_running:
        test_bot.stop()
