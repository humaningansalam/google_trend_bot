from unittest.mock import Mock, MagicMock
import pytest
from datetime import datetime
from prometheus_client import REGISTRY
from playwright.sync_api import sync_playwright

from myapp.src.main import create_app
from myapp.src.bot.GoogleTrendsRSSBot import Bot
from myapp.src.bot.GoogleTrendsScraper import Scraper

@pytest.fixture
def mock_rss_parser():
    parser = Mock()
    parser.parse.return_value = [
        {
            'title': 'Test Trend',
            'content': 'Test Content',
            'link': 'http://test.com',
            'published': '2024-01-01',
            'parsed_time': datetime(2024, 1, 1, 0, 0, 0)
        }
    ]
    return parser

@pytest.fixture
def mock_slack_sender():
    sender = Mock()
    sender.send_message.return_value = True
    return sender

@pytest.fixture
def mock_flogger():
    logger = Mock()
    return logger

@pytest.fixture
def mock_pmetrics():
    metrics = Mock()
    metrics.request_time = MagicMock()
    metrics.request_time.time.return_value.__enter__ = lambda x: None
    metrics.request_time.time.return_value.__exit__ = lambda x, y, z, a: None
    return metrics

@pytest.fixture
def test_bot(mock_rss_parser, mock_slack_sender, mock_flogger, mock_pmetrics):
    return Bot(
        mock_rss_parser,
        mock_slack_sender,
        mock_flogger,
        mock_pmetrics,
        interval=10
    )

@pytest.fixture
def mock_page():
    page = Mock()
    page.goto = Mock()
    page.query_selector = Mock(return_value=Mock(inner_text=Mock(return_value="Test Trend")))
    page.query_selector_all = Mock(return_value=[Mock()])
    page.wait_for_selector = Mock()
    return page

@pytest.fixture
def test_scraper(monkeypatch):
    scraper = Scraper()
    scraper.scrape_trends = Mock(return_value=[{'trend': 'Test Trend'}])
    return scraper

@pytest.fixture
def app(test_bot, test_scraper):
    app = create_app(bot=test_bot, scraper=test_scraper)
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def get_counter_value():
    def _get_counter_value(counter_name, label_values):
        for metric in REGISTRY.collect():
            if metric.name == counter_name:
                for sample in metric.samples:
                    if sample.labels == label_values:
                        return sample.value
        return None
    return _get_counter_value


@pytest.fixture(scope="function", autouse=True)
def cleanup_bot(test_bot):
    """테스트 종료 시 Bot 인스턴스를 안전하게 종료"""
    yield
    if test_bot.is_running:
        test_bot.stop()