import logging

from playwright.async_api import BrowserContext, ElementHandle, Locator, Page

TRENDS_PAGE_URL = "https://trends.google.co.kr/trending?geo=KR&hl=ko&hours=24"
TREND_TABLE_SELECTOR = "tbody[jsname='cC57zf']"
TREND_ROW_SELECTOR = f"{TREND_TABLE_SELECTOR} tr[jsname='oKdM2c']"
NEXT_PAGE_BUTTON_SELECTOR = "button[jsname='ViaHrd']"
TITLE_SELECTOR = ".mZ3RIc"
VOLUME_SELECTOR = ".lqv0Cb"
DETAIL_PANEL_SELECTOR = ".EMz5P"
ANALYSIS_SELECTOR = "span[jsname='V67aGc']:not([aria-hidden='true'])"
NEWS_CARD_SELECTOR = "div[jsaction='click:vx9mmb;contextmenu:rbJKIe']"
NEWS_TITLE_SELECTOR = ".QbLC8c"
MAX_PAGES = 5
PAGE_TRANSITION_DELAY_MS = 2_000

logger = logging.getLogger(__name__)


async def crawl(
    page: Page,
    _context: BrowserContext,
    job_path: str | None,
) -> dict[str, object]:
    logger.info("Crawling Google Trends; job_path=%s", job_path)
    await page.goto(
        TRENDS_PAGE_URL,
        wait_until="domcontentloaded",
        timeout=90_000,
    )
    await page.wait_for_selector(TREND_TABLE_SELECTOR, timeout=60_000)

    trends: list[dict[str, object]] = []
    discovered_row_count = 0

    for page_number in range(1, MAX_PAGES + 1):
        trend_rows = await page.query_selector_all(TREND_ROW_SELECTOR)
        discovered_row_count += len(trend_rows)

        for row_number, trend_row in enumerate(trend_rows, start=1):
            try:
                trend = await _extract_trend_row(page, trend_row)
            except Exception:
                logger.warning(
                    "Could not extract trend row %s on page %s",
                    row_number,
                    page_number,
                    exc_info=True,
                )
                continue

            trends.append(trend)
            logger.info(
                "Collected trend %s: %s",
                len(trends),
                trend["트렌드 제목"],
            )

        next_page_button = await page.query_selector(NEXT_PAGE_BUTTON_SELECTOR)
        if next_page_button is None or await next_page_button.is_disabled():
            break
        if page_number == MAX_PAGES:
            logger.warning("Reached the crawl limit of %s pages", MAX_PAGES)
            break

        await next_page_button.click()
        await page.wait_for_timeout(PAGE_TRANSITION_DELAY_MS)

    if discovered_row_count and not trends:
        raise RuntimeError(
            f"Failed to extract any of {discovered_row_count} discovered trend rows"
        )

    logger.info("Finished Google Trends crawl with %s items", len(trends))
    return {"status": "success", "data": trends}


async def _extract_trend_row(
    page: Page,
    trend_row: ElementHandle,
) -> dict[str, object]:
    title_element = await trend_row.query_selector(TITLE_SELECTOR)
    if title_element is None:
        raise ValueError("Trend row is missing a title")

    trend_title = await title_element.inner_text()
    await trend_row.click()

    detail_panel = page.locator(DETAIL_PANEL_SELECTOR).filter(
        has=page.get_by_role("heading", name=trend_title, exact=True)
    )
    await detail_panel.wait_for(state="visible", timeout=15_000)

    volume_element = await trend_row.query_selector(VOLUME_SELECTOR)
    search_volume = await volume_element.inner_text() if volume_element else "N/A"
    analysis = await detail_panel.locator(ANALYSIS_SELECTOR).all_inner_texts()
    news_articles = await _extract_news_articles(detail_panel)

    return {
        "트렌드 제목": trend_title,
        "검색량": search_volume,
        "트렌드 분석": analysis,
        "뉴스 데이터": news_articles,
    }


async def _extract_news_articles(
    detail_panel: Locator,
) -> list[dict[str, str]]:
    articles: list[dict[str, str]] = []
    news_cards = await detail_panel.locator(NEWS_CARD_SELECTOR).all()
    for news_card in news_cards:
        title = news_card.locator(NEWS_TITLE_SELECTOR).first
        link = news_card.locator("a").first
        if not await title.count() or not await link.count():
            continue

        article_url = await link.get_attribute("href")
        if not article_url:
            continue
        articles.append(
            {
                "뉴스 제목": await title.inner_text(),
                "URL": article_url,
            }
        )
    return articles
