import asyncio
from unittest.mock import Mock

from src.bot import scraper as scraper_module
from src.bot.scraper import Scraper
from src.clients.playwright_submit import (
    JobResultEnvelope,
    RemoteJobErrorCode,
    RemoteJobResult,
)
from src.common.scrape_contracts import ScrapeErrorCode, ScrapeResult
from src.config import ScraperBackend


def test_scrape_result_accepts_the_canonical_success_schema(monkeypatch):
    scraper = Scraper()

    async def local_result():
        return ScrapeResult.from_wire(
            {"status": "success", "data": [{"trend": "Test Trend"}]}
        )

    monkeypatch.setattr(scraper, "_scrape_local", local_result)

    result = asyncio.run(scraper.scrape_trends())

    assert result == ScrapeResult.success([{"trend": "Test Trend"}])


def test_scrape_result_rejects_a_response_without_explicit_status():
    result = ScrapeResult.from_wire({"error": "unstructured error"})

    assert result.error.code is ScrapeErrorCode.INVALID_RESPONSE


def test_scrape_result_validates_success_data_shape():
    result = ScrapeResult.from_wire({"status": "success", "data": "invalid"})

    assert result.error.code is ScrapeErrorCode.INVALID_RESPONSE


def test_scrape_result_rejects_noncanonical_alias_fields():
    success = ScrapeResult.from_wire(
        {"status": "success", "data": [], "message": "legacy alias"}
    )
    error = ScrapeResult.from_wire(
        {
            "status": "error",
            "error": {
                "code": "crawl_failed",
                "message": "boom",
                "detail": "legacy alias",
            },
        }
    )

    assert success.error.code is ScrapeErrorCode.INVALID_RESPONSE
    assert error.error.code is ScrapeErrorCode.INVALID_RESPONSE


def test_local_browser_failure_returns_a_typed_error(monkeypatch):
    class BrokenPlaywright:
        async def __aenter__(self):
            raise RuntimeError("browser unavailable")

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        scraper_module,
        "async_playwright",
        lambda: BrokenPlaywright(),
    )

    result = asyncio.run(Scraper().scrape_trends())

    assert result.error.code is ScrapeErrorCode.CRAWL_FAILED
    assert result.error.message == "Local browser crawl failed: browser unavailable"


def test_remote_scraper_maps_typed_job_errors():
    job_client = Mock()
    job_client.execute.return_value = RemoteJobResult.failure(
        RemoteJobErrorCode.JOB_TIMEOUT,
        "poll limit reached",
    )
    scraper = Scraper(
        backend=ScraperBackend.REMOTE,
        job_client=job_client,
    )

    result = asyncio.run(scraper.scrape_trends())

    assert result.error.code is ScrapeErrorCode.REMOTE_JOB_TIMEOUT
    assert result.error.message == "poll limit reached"


def test_remote_scraper_decodes_the_canonical_wire_result():
    job_client = Mock()
    job_client.execute.return_value = RemoteJobResult.success(
        JobResultEnvelope(
            payload={
                "status": "success",
                "data": [{"trend": "Remote Trend"}],
            },
            files={"artifact.txt": "/api/jobs/download/1"},
        )
    )
    scraper = Scraper(
        backend=ScraperBackend.REMOTE,
        job_client=job_client,
    )

    result = asyncio.run(scraper.scrape_trends())

    assert result == ScrapeResult.success([{"trend": "Remote Trend"}])


def test_scraper_module_entrypoint_serializes_the_public_result(monkeypatch, capsys):
    async def scrape_trends(self):
        return ScrapeResult.success([{"trend": "Entry Trend"}])

    monkeypatch.setattr(Scraper, "scrape_trends", scrape_trends)

    scraper_module.main()

    expected = "{'status': 'success', 'data': [{'trend': 'Entry Trend'}]}"
    assert capsys.readouterr().out.strip() == expected
