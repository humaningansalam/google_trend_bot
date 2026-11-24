import asyncio
import logging
from pathlib import Path

from playwright.async_api import async_playwright

from src.clients.playwright_submit import (
    PlaywrightJobClient,
    RemoteJobErrorCode,
)
from src.common.scrape_contracts import ScrapeErrorCode, ScrapeResult
from src.config import ScraperBackend
from src.crawl_scripts.google_trends_crawl import crawl

CRAWL_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "crawl_scripts" / "google_trends_crawl.py"
)
REMOTE_JOB_NAME = "google_trends_crawl"
REMOTE_ERROR_CODES = {
    RemoteJobErrorCode.SCRIPT_NOT_FOUND: ScrapeErrorCode.REMOTE_SCRIPT_NOT_FOUND,
    RemoteJobErrorCode.SUBMISSION_FAILED: ScrapeErrorCode.REMOTE_SUBMISSION_FAILED,
    RemoteJobErrorCode.INVALID_RESPONSE: ScrapeErrorCode.INVALID_RESPONSE,
    RemoteJobErrorCode.JOB_NOT_FOUND: ScrapeErrorCode.REMOTE_JOB_NOT_FOUND,
    RemoteJobErrorCode.JOB_FAILED: ScrapeErrorCode.REMOTE_JOB_FAILED,
    RemoteJobErrorCode.JOB_CANCELLED: ScrapeErrorCode.REMOTE_JOB_CANCELLED,
    RemoteJobErrorCode.JOB_INTERRUPTED: ScrapeErrorCode.REMOTE_JOB_INTERRUPTED,
    RemoteJobErrorCode.JOB_TIMEOUT: ScrapeErrorCode.REMOTE_JOB_TIMEOUT,
    RemoteJobErrorCode.RESULT_NOT_READY: ScrapeErrorCode.REMOTE_RESULT_NOT_READY,
    RemoteJobErrorCode.REMOTE_UNAVAILABLE: ScrapeErrorCode.REMOTE_UNAVAILABLE,
}


class GoogleTrendsScraper:
    def __init__(
        self,
        backend: ScraperBackend = ScraperBackend.LOCAL,
        job_client: PlaywrightJobClient | None = None,
    ) -> None:
        self._backend = backend
        self._job_client = job_client
        self._logger = logging.getLogger(__name__)

    async def scrape_trends(self) -> ScrapeResult:
        if self._backend is ScraperBackend.REMOTE:
            return await asyncio.to_thread(self._scrape_remote)
        return await self._scrape_local()

    async def _scrape_local(self) -> ScrapeResult:
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    context = await browser.new_context()
                    page = await context.new_page()
                    payload = await crawl(page, context, None)
                    return ScrapeResult.from_payload(payload)
                finally:
                    await browser.close()
        except Exception:
            self._logger.exception("Local Google Trends crawl failed")
            return ScrapeResult.failure(
                ScrapeErrorCode.CRAWL_FAILED,
                "Local browser crawl failed",
            )

    def _scrape_remote(self) -> ScrapeResult:
        job_client = self._job_client or PlaywrightJobClient()
        remote_result = job_client.execute(
            CRAWL_SCRIPT_PATH,
            REMOTE_JOB_NAME,
        )
        if remote_result.is_success:
            return ScrapeResult.from_payload(remote_result.value)

        error = remote_result.error
        if error is None:
            raise AssertionError("Failed remote job is missing its error")
        return ScrapeResult.failure(
            REMOTE_ERROR_CODES[error.code],
            error.message,
        )


def main() -> None:
    result = asyncio.run(GoogleTrendsScraper().scrape_trends())
    print(result.to_payload())


if __name__ == "__main__":
    main()
