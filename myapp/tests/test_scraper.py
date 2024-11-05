from unittest.mock import Mock
from playwright.sync_api import sync_playwright

from myapp.src.bot.GoogleTrendsScraper import Scraper

def test_scraper_initialization(test_scraper):
    assert isinstance(test_scraper, Scraper)

def test_setup_browser(test_scraper):
    with sync_playwright() as playwright:
        browser, context = test_scraper.setup_browser(playwright)
        assert browser is not None
        assert context is not None

def test_scrape_trends(test_scraper):
    data = test_scraper.scrape_trends()
    assert isinstance(data, list)
    assert data == [{'trend': 'Test Trend'}]

def test_extract_trend_data(test_scraper, mock_page):
    mock_tr = Mock()
    mock_tr.query_selector = Mock(return_value=Mock(
        inner_text=Mock(return_value="Test Trend")
    ))
    
    data = test_scraper._extract_trend_data(mock_tr, mock_page)
    assert isinstance(data, dict)
    assert "트렌드 제목" in data
    assert data["트렌드 제목"] == "Test Trend"