import asyncio
import os

from playwright.async_api import async_playwright

from src.clients.playwright_submit import (
    PlaywrightJobClient,
    RemoteJobErrorCode,
)
from src.common.scrape_contracts import ScrapeErrorCode, ScrapeResult
from src.config import ScraperBackend
from src.crawl_scripts.google_trends_crawl import crawl


REMOTE_ERROR_CODES = {
    RemoteJobErrorCode.SCRIPT_NOT_FOUND: ScrapeErrorCode.REMOTE_SCRIPT_NOT_FOUND,
    RemoteJobErrorCode.SUBMISSION_FAILED: ScrapeErrorCode.REMOTE_SUBMISSION_FAILED,
    RemoteJobErrorCode.INVALID_RESPONSE: ScrapeErrorCode.INVALID_RESPONSE,
    RemoteJobErrorCode.JOB_NOT_FOUND: ScrapeErrorCode.REMOTE_JOB_NOT_FOUND,
    RemoteJobErrorCode.JOB_FAILED: ScrapeErrorCode.REMOTE_JOB_FAILED,
    RemoteJobErrorCode.JOB_TIMEOUT: ScrapeErrorCode.REMOTE_JOB_TIMEOUT,
    RemoteJobErrorCode.RESULT_NOT_READY: ScrapeErrorCode.REMOTE_RESULT_NOT_READY,
    RemoteJobErrorCode.REMOTE_UNAVAILABLE: ScrapeErrorCode.REMOTE_UNAVAILABLE,
    RemoteJobErrorCode.DOWNLOAD_FAILED: ScrapeErrorCode.REMOTE_DOWNLOAD_FAILED,
}


class Scraper:
    def __init__(
        self,
        backend: ScraperBackend = ScraperBackend.LOCAL,
        job_client: PlaywrightJobClient | None = None,
    ):
        self.backend = backend
        self.job_client = job_client or PlaywrightJobClient()

    async def scrape_trends(self) -> ScrapeResult:
        if self.backend is ScraperBackend.REMOTE:
            return await asyncio.to_thread(self._scrape_remote)
        return await self._scrape_local()

    async def _scrape_local(self) -> ScrapeResult:
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                try:
                    return ScrapeResult.from_wire(
                        await crawl(page, context, None)
                    )
                finally:
                    await browser.close()
        except Exception as exc:
            return ScrapeResult.failure(
                ScrapeErrorCode.CRAWL_FAILED,
                f"Local browser crawl failed: {exc}",
            )

    def _scrape_remote(self) -> ScrapeResult:
        script_path = os.path.normpath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "crawl_scripts",
                "google_trends_crawl.py",
            )
        )
        remote_result = self.job_client.execute(
            script_path, "google_trends_crawl"
        )
        if remote_result.is_success:
            return ScrapeResult.from_wire(remote_result.value.payload)

        error = remote_result.error
        return ScrapeResult.failure(
            REMOTE_ERROR_CODES[error.code],
            error.message,
        )


def main():
    result = asyncio.run(Scraper().scrape_trends())
    print(result.to_wire())


if __name__ == "__main__":
    main()
