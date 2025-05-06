from unittest.mock import Mock, AsyncMock 

from myapp.src.bot.GoogleTrendsScraper import Scraper

def test_scraper_initialization(test_scraper):
    assert isinstance(test_scraper, Scraper)

