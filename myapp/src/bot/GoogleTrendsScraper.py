import os
import time
import pandas as pd
from myapp.src.crawl_scripts.google_trends_crawl import crawl
from myapp.src.clients.playwright_submit import submit_job, poll_job_status, get_job_results
from playwright.async_api import async_playwright

class Scraper:
    def __init__(self):
        pass

    async def _get_raw_scrape_result(self):
        """로컬 또는 서버에서 크롤링 결과를 가져오는 내부 헬퍼 메소드.
           crawl.py의 반환값과 동일한 형식의 dict를 반환 (예: {'status': 'success', 'data': [...]})
           또는 에러 발생 시 {'error': '...'} 형태의 dict를 반환.
        """
        use_server = os.getenv('USE_SERVER', 'false').lower() == 'true'
        if use_server:
            return self.submit_to_server("google_trends_crawl")
        else:
            return await self.scrape_trends_local()

    async def scrape_trends(self):
        """
        트렌드 데이터를 가져오는 메소드.
        최종적으로 실제 트렌드 데이터 리스트 또는 에러 정보를 담은 dict를 반환.
        """
        raw_result = await self._get_raw_scrape_result()

        if not isinstance(raw_result, dict):
            return {"error": f"Scraping did not return a dictionary: {raw_result}"}

        if raw_result.get('status') == 'success' and 'data' in raw_result:
            return raw_result['data']
        elif 'error' in raw_result:
            return {"error": raw_result['error']}
        else:
            return {"error": f"Scraping failed or returned unexpected format: {raw_result}"}

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
        script_path = "myapp/src/crawl_scripts/google_trends_crawl.py"
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