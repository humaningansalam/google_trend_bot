import asyncio

from src.bot import scraper as scraper_module
from src.bot.scraper import Scraper


def test_scraper_initialization(test_scraper):
    assert isinstance(test_scraper, Scraper)


def test_scraper_success_shape(monkeypatch):
    scraper = Scraper()

    async def raw_result():
        return {"status": "success", "data": [{"trend": "Test Trend"}]}

    monkeypatch.setattr(scraper, "_get_raw_scrape_result", raw_result)

    result = asyncio.run(scraper.scrape_trends())
    assert result == {"status": "success", "data": [{"trend": "Test Trend"}]}


def test_scraper_error_shape(monkeypatch):
    scraper = Scraper()

    async def raw_result():
        return {"status": "error", "message": "boom"}

    monkeypatch.setattr(scraper, "_get_raw_scrape_result", raw_result)

    result = asyncio.run(scraper.scrape_trends())
    assert result == {"status": "error", "message": "boom"}


def test_scraper_module_entrypoint_awaits_scrape(monkeypatch, capsys):
    async def scrape_trends(self):
        return {"status": "success", "data": [{"trend": "Entry Trend"}]}

    monkeypatch.setattr(Scraper, "scrape_trends", scrape_trends)

    scraper_module.main()

    expected = "{'status': 'success', 'data': [{'trend': 'Entry Trend'}]}"
    assert capsys.readouterr().out.strip() == expected
