import logging

from playwright.async_api import BrowserContext, Page


async def crawl(page: Page, context: BrowserContext, job_path: str):
    """구글 트렌드 크롤링 함수"""
    try:
        logging.info(f"Crawling Google Trends. Job path: {job_path}")

        await page.goto(
            "https://trends.google.co.kr/trending?geo=KR&hl=ko&hours=24",
            wait_until="domcontentloaded",
            timeout=90000,
        )
        await page.wait_for_selector("tbody[jsname='cC57zf']", timeout=60000)

        data = []
        rows_discovered = 0
        max_pages = 5
        current_page = 1
        while current_page <= max_pages:
            tr_elements = await page.query_selector_all(
                "tbody[jsname='cC57zf'] tr[jsname='oKdM2c']"
            )
            rows_discovered += len(tr_elements)

            for tr_index, tr in enumerate(tr_elements):
                try:
                    trend_data = await _extract_trend_data(page, tr)
                except Exception as row_error:
                    logging.warning(
                        "Error extracting trend item "
                        f"{tr_index + 1}: {row_error}"
                    )
                    continue

                data.append(trend_data)
                logging.info(
                    "Collected item %s: %s",
                    len(data),
                    trend_data.get("트렌드 제목"),
                )

            next_button = await page.query_selector("button[jsname='ViaHrd']")
            if not next_button:
                logging.info("Next button not found. Assuming end of pages.")
                break
            if await next_button.is_disabled():
                logging.info("Next button is disabled. Assuming end of pages.")
                break
            if current_page >= max_pages:
                logging.warning("Reached max_pages=%s. Stopping crawl.", max_pages)
                break

            logging.info("Next button is active. Clicking to go to the next page.")
            await next_button.click()
            await page.wait_for_timeout(2000)
            current_page += 1

        if rows_discovered and not data:
            message = (
                "Failed to extract any of "
                f"{rows_discovered} discovered trend rows"
            )
            logging.error(message)
            raise RuntimeError(message)

        logging.info("Finished crawling. Collected %s items.", len(data))
        return {"status": "success", "data": data}
    except Exception as error:
        logging.error("Crawl error: %s", error, exc_info=True)
        raise


async def _extract_trend_data(page, tr):
    """트렌드 행을 열고 연결된 상세 패널에서 데이터를 추출한다."""
    title_elem = await tr.query_selector(".mZ3RIc")
    if not title_elem:
        raise ValueError("Trend row is missing a title")

    trend_title = await title_elem.inner_text()
    await tr.click()

    detail_panel = page.locator(".EMz5P").filter(
        has=page.get_by_role("heading", name=trend_title, exact=True)
    )
    await detail_panel.wait_for(state="visible", timeout=15000)

    volume_elem = await tr.query_selector(".lqv0Cb")
    search_volume = await volume_elem.inner_text() if volume_elem else "N/A"

    analysis_selector = "span[jsname='V67aGc']:not([aria-hidden='true'])"
    trend_analysis = await detail_panel.locator(
        analysis_selector
    ).all_inner_texts()

    news_data = []
    news_elems = await detail_panel.locator(
        "div[jsaction='click:vx9mmb;contextmenu:rbJKIe']"
    ).all()
    for news in news_elems:
        title_elem = news.locator(".QbLC8c").first
        link_elem = news.locator("a").first
        if await title_elem.count() and await link_elem.count():
            news_data.append(
                {
                    "뉴스 제목": await title_elem.inner_text(),
                    "URL": await link_elem.get_attribute("href"),
                }
            )

    return {
        "트렌드 제목": trend_title,
        "검색량": search_volume,
        "트렌드 분석": trend_analysis,
        "뉴스 데이터": news_data,
    }
