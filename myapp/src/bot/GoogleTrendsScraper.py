import os
import time
import pandas as pd
from myapp.src.caawl_scripts.google_trends_crawl import crawl
from myapp.src.clients.playwright_submit import submit_job, poll_job_status, get_job_results
from playwright.async_api import async_playwright

class Scraper:
    def __init__(self):
        pass

    async def scrape_trends(self):
        """
        트렌드 데이터를 가져오는 메소드. 로컬 또는 서버에서 실행 가능.
        환경 변수 'USE_SERVER'가 'true'이면 서버로 제출, 아니면 로컬에서 실행.
        """
        use_server = os.getenv('USE_SERVER', 'false').lower() == 'true'

        if use_server:
            return self.submit_to_server("google_trends_crawl")
        else:
            return await self.scrape_trends_local()

    async def scrape_trends_local(self):
        """
        로컬에서 Playwright를 사용하여 트렌드 데이터를 스크랩합니다.
        """
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            try:
                job_path = None
                # await 로 crawl 함수 호출
                data_dict = await crawl(page, context, job_path)
                # 로컬에서는 실제 데이터만 반환하거나, 전체 dict 반환 결정
                if data_dict.get('status') == 'success':
                    return data_dict
                else:
                    return {"error": data_dict.get('error', 'Crawling failed locally')}
            finally:
                await browser.close() 

    def submit_to_server(self, job_name: str):
        """
        crawl.py를 서버에 제출하여 크롤링 작업을 수행하도록 합니다.
        """
        script_path = "../crawl_scripts/crawl.py"
        job_id = submit_job(script_path, job_name)
        if job_id:
            final_status = poll_job_status(job_id)
            if final_status == 'COMPLETED':
                results = get_job_results(job_id)
                return results.get('result') if results else {"error": "No results returned"}
            else:
                return {"error": f"Job did not complete successfully. Final status: {final_status}"}
        else:
            return {"error": "Failed to submit job."}

if __name__ == "__main__":
    app = Scraper()

    trends_data = app.scrape_trends()
    print(trends_data)