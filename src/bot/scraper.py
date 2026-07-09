import asyncio
import os

from playwright.async_api import async_playwright

from src.clients.playwright_submit import get_job_results, poll_job_status, submit_job
from src.crawl_scripts.google_trends_crawl import crawl


class Scraper:
    def __init__(self):
        pass

    async def _get_raw_scrape_result(self):
        use_server = os.getenv("USE_SERVER", "false").lower() == "true"
        if use_server:
            return self.submit_to_server("google_trends_crawl")
        return await self.scrape_trends_local()

    async def scrape_trends(self):
        raw_result = await self._get_raw_scrape_result()

        if not isinstance(raw_result, dict):
            return {"status": "error", "message": f"Scraping did not return a dictionary: {raw_result}"}

        if raw_result.get("status") == "success" and "data" in raw_result:
            return {"status": "success", "data": raw_result["data"]}

        if raw_result.get("status") == "error" and "message" in raw_result:
            return {"status": "error", "message": raw_result["message"]}

        if "error" in raw_result:
            return {"status": "error", "message": raw_result["error"]}

        return {"status": "error", "message": f"Scraping failed or returned unexpected format: {raw_result}"}

    async def scrape_trends_local(self):
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            try:
                job_path = None
                data_dict = await crawl(page, context, job_path)
                if data_dict.get("status") == "success":
                    return data_dict
                return {"status": "error", "message": data_dict.get("message", data_dict.get("error", "Crawling failed locally"))}
            finally:
                await browser.close()

    def submit_to_server(self, job_name: str):
        script_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "crawl_scripts",
            "google_trends_crawl.py",
        )
        script_path = os.path.normpath(script_path)
        job_id = submit_job(script_path, job_name)
        if job_id:
            final_status = poll_job_status(job_id)
            if final_status == "COMPLETED":
                results = get_job_results(job_id)
                result = results.get("result") if results else None
                if isinstance(result, dict) and result.get("status") == "success":
                    return result
                if isinstance(result, dict):
                    return {"status": "error", "message": result.get("message", result.get("error", "Scraping failed on server"))}
                return {"status": "error", "message": "No results returned"}
            # FAILED/TIMEOUT: try to get detailed error from server
            results = get_job_results(job_id)
            result = results.get("result") if results else None
            if isinstance(result, dict) and "message" in result:
                return {"status": "error", "message": result["message"]}
            if isinstance(result, dict) and "error" in result:
                return {"status": "error", "message": result["error"]}
            return {"status": "error", "message": f"Job did not complete successfully. Final status: {final_status}"}
        return {"status": "error", "message": "Failed to submit job."}


def main():
    app = Scraper()
    trends_data = asyncio.run(app.scrape_trends())
    print(trends_data)


if __name__ == "__main__":
    main()
