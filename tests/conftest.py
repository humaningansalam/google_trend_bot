from unittest.mock import Mock, MagicMock, patch, AsyncMock
import pytest
from datetime import datetime
from prometheus_client import REGISTRY

from src.main import create_app
from src.bot.rss_bot import RSSBot
from src.bot.scraper import Scraper

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
def mock_send_alert():
    """his_mon.send_alert 함수 모킹"""
    with patch('src.bot.rss_bot.send_alert') as mock:
        yield mock

@pytest.fixture
def test_bot(mock_rss_parser, mock_send_alert):
    """테스트용 RSSBot 인스턴스 생성"""
    return RSSBot(
        rss_parser=mock_rss_parser,
        interval=10
    )

@pytest.fixture
def test_scraper():
    scraper = Scraper()
    scraper.scrape_trends = AsyncMock(return_value=[{'trend': 'Test Trend'}])
    return scraper

@pytest.fixture
def app(test_bot, test_scraper):
    app = create_app(bot=test_bot, scraper=test_scraper)
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture(scope="function", autouse=True)
def cleanup_bot(test_bot):
    """테스트 종료 시 Bot 종료"""
    yield
    if test_bot.is_running:
        test_bot.stop()