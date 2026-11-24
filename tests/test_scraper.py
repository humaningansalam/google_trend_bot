import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.bot import scraper as scraper_module
from src.bot.scraper import GoogleTrendsScraper
from src.clients.playwright_submit import RemoteJobErrorCode, RemoteJobResult
from src.common.scrape_contracts import ScrapeErrorCode, ScrapeResult
from src.config import ScraperBackend


def test_scrape_result_accepts_the_canonical_success_schema():
    result = ScrapeResult.from_payload(
        {"status": "success", "data": [{"trend": "Test Trend"}]}
    )

    assert result == ScrapeResult.success([{"trend": "Test Trend"}])


def test_scrape_result_rejects_a_response_without_explicit_status():
    result = ScrapeResult.from_payload({"error": "unstructured error"})

    assert result.error is not None
    assert result.error.code is ScrapeErrorCode.INVALID_RESPONSE


def test_scrape_result_validates_success_data_shape():
    result = ScrapeResult.from_payload({"status": "success", "data": "invalid"})

    assert result.error is not None
    assert result.error.code is ScrapeErrorCode.INVALID_RESPONSE


def test_scrape_result_rejects_noncanonical_alias_fields():
    success = ScrapeResult.from_payload(
        {"status": "success", "data": [], "message": "legacy alias"}
    )
    error = ScrapeResult.from_payload(
        {
            "status": "error",
            "error": {
                "code": "crawl_failed",
                "message": "boom",
                "detail": "legacy alias",
            },
        }
    )

    assert success.error is not None
    assert success.error.code is ScrapeErrorCode.INVALID_RESPONSE
    assert error.error is not None
    assert error.error.code is ScrapeErrorCode.INVALID_RESPONSE


def test_local_browser_failure_returns_a_generic_typed_error(monkeypatch):
    class BrokenPlaywright:
        async def __aenter__(self):
            raise RuntimeError("browser unavailable at /private/path")

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        scraper_module,
        "async_playwright",
        BrokenPlaywright,
    )

    result = asyncio.run(GoogleTrendsScraper().scrape_trends())

    assert result.error is not None
    assert result.error.code is ScrapeErrorCode.CRAWL_FAILED
    assert result.error.message == "Local browser crawl failed"


def test_local_scraper_closes_the_browser_when_context_creation_fails(
    monkeypatch,
):
    browser = Mock()
    browser.new_context = AsyncMock(side_effect=RuntimeError("context creation failed"))
    browser.close = AsyncMock()

    chromium = Mock()
    chromium.launch = AsyncMock(return_value=browser)
    playwright = Mock(chromium=chromium)

    class WorkingPlaywright:
        async def __aenter__(self):
            return playwright

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(
        scraper_module,
        "async_playwright",
        WorkingPlaywright,
    )

    result = asyncio.run(GoogleTrendsScraper().scrape_trends())

    assert result.error is not None
    assert result.error.code is ScrapeErrorCode.CRAWL_FAILED
    browser.close.assert_awaited_once_with()


def test_remote_scraper_maps_typed_job_errors():
    job_client = Mock()
    job_client.execute.return_value = RemoteJobResult.failure(
        RemoteJobErrorCode.JOB_TIMEOUT,
        "poll limit reached",
    )
    scraper = GoogleTrendsScraper(
        backend=ScraperBackend.REMOTE,
        job_client=job_client,
    )

    result = asyncio.run(scraper.scrape_trends())

    assert result.error is not None
    assert result.error.code is ScrapeErrorCode.REMOTE_JOB_TIMEOUT
    assert result.error.message == "poll limit reached"


@pytest.mark.parametrize(
    ("remote_code", "expected_code"),
    [
        (
            RemoteJobErrorCode.JOB_CANCELLED,
            ScrapeErrorCode.REMOTE_JOB_CANCELLED,
        ),
        (
            RemoteJobErrorCode.JOB_INTERRUPTED,
            ScrapeErrorCode.REMOTE_JOB_INTERRUPTED,
        ),
    ],
)
def test_remote_scraper_maps_terminal_lifecycle_errors(
    remote_code: RemoteJobErrorCode,
    expected_code: ScrapeErrorCode,
):
    job_client = Mock()
    job_client.execute.return_value = RemoteJobResult.failure(
        remote_code,
        "remote lifecycle ended",
    )
    scraper = GoogleTrendsScraper(
        backend=ScraperBackend.REMOTE,
        job_client=job_client,
    )

    result = asyncio.run(scraper.scrape_trends())

    assert result.error is not None
    assert result.error.code is expected_code
    assert result.error.message == "remote lifecycle ended"


def test_remote_scraper_decodes_the_canonical_payload():
    job_client = Mock()
    job_client.execute.return_value = RemoteJobResult.success(
        {
            "status": "success",
            "data": [{"trend": "Remote Trend"}],
        }
    )
    scraper = GoogleTrendsScraper(
        backend=ScraperBackend.REMOTE,
        job_client=job_client,
    )

    result = asyncio.run(scraper.scrape_trends())

    assert result == ScrapeResult.success([{"trend": "Remote Trend"}])


def test_module_entrypoint_prints_the_public_payload(monkeypatch, capsys):
    async def scrape_trends(_self):
        return ScrapeResult.success([{"trend": "Entry Trend"}])

    monkeypatch.setattr(GoogleTrendsScraper, "scrape_trends", scrape_trends)

    scraper_module.main()

    expected = "{'status': 'success', 'data': [{'trend': 'Entry Trend'}]}"
    assert capsys.readouterr().out.strip() == expected
