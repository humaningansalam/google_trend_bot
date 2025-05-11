# crawl.py
from playwright.async_api import Page, BrowserContext
import logging
import os

async def crawl(page: Page, context: BrowserContext, job_path: str):
    """구글 트렌드 크롤링 함수 """
    try:
        logging.info(f"Crawling Google Trends. Job path: {job_path}")
        
        # 페이지 이동 및 초기 설정
        await page.goto(
            "https://trends.google.co.kr/trending?geo=KR&hl=ko&hours=24",
            wait_until="domcontentloaded",
            timeout=90000
        )
        await page.wait_for_selector("tbody[jsname='cC57zf']", timeout=60000)

        # 크롤링 실행
        data = []
        while True:
            tr_elements = await page.query_selector_all("tbody[jsname='cC57zf'] tr[jsname='oKdM2c']")
            
            items_processed_on_this_page = 0
            for tr_index, tr in enumerate(tr_elements): 
                try:
                    await tr.click()
                    await page.wait_for_selector(".EMz5P", timeout=15000)
                except Exception as e_click_wait:
                    logging.warning(f"Error clicking or waiting for details on item {tr_index + 1} on page {page_num}: {e_click_wait}")
                    continue 

                trend_data = await _extract_trend_data(tr, page)
                data.append(trend_data)
                items_processed_on_this_page += 1
                logging.info(f"Collected item {len(data)}: {trend_data.get('트렌드 제목')}")

            # 다음 페이지로 넘어갈지 결정
            next_button = await page.query_selector("button[jsname='ViaHrd']")

            if not next_button:
                logging.info("Next button not found. Assuming end of pages.")
                break 

            is_next_button_disabled = await next_button.is_disabled()
            if is_next_button_disabled:
                logging.info("Next button is disabled. Assuming end of pages.")
                break 

            logging.info("Next button is active. Clicking to go to the next page.")
            await next_button.click()
            await page.wait_for_timeout(2000) 

        logging.info(f"Finished crawling. Collected {len(data)} items.")
        return {
            'status': 'success',
            'data': data,
            'screenshot': 'trend_screenshot.png'
        }

    except Exception as e:
        logging.error(f"Crawl error: {str(e)}", exc_info=True)
        return {'error': str(e)}

async def _extract_trend_data(tr, page):
    """트렌드 데이터 추출"""
    title_elem = await tr.query_selector(".mZ3RIc")
    volume_elem = await tr.query_selector(".lqv0Cb")
    
    trend_title = await title_elem.inner_text() if title_elem else "N/A"
    search_volume = await volume_elem.inner_text() if volume_elem else "N/A"

    # 트렌드 분석 데이터
    emz5p = await page.query_selector(".EMz5P")
    analysis_elems = await emz5p.query_selector_all("div.HLcRPe span[jsname='V67aGc']")
    trend_analysis = [await elem.inner_text() for elem in analysis_elems]

    # 뉴스 데이터
    news_data = []
    news_elems = await emz5p.query_selector_all("div[jsaction='click:vx9mmb;contextmenu:rbJKIe']")
    for news in news_elems:
        title_elem = await news.query_selector(".QbLC8c")
        link_elem = await news.query_selector("a")
        
        if title_elem and link_elem:
            news_title = await title_elem.inner_text()
            news_url = await link_elem.get_attribute("href")
            news_data.append({"뉴스 제목": news_title, "URL": news_url})

    return {
        "트렌드 제목": trend_title,
        "검색량": search_volume,
        "트렌드 분석": trend_analysis,
        "뉴스 데이터": news_data
    }