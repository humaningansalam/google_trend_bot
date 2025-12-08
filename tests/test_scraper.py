from src.bot.scraper import Scraper

def test_scraper_initialization(test_scraper):
    assert isinstance(test_scraper, Scraper)