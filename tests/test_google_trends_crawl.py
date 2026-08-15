import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.crawl_scripts.google_trends_crawl import crawl


def test_crawl_extracts_a_trend_row():
    title_element = Mock()
    title_element.inner_text = AsyncMock(return_value="Target Trend")
    volume_element = Mock()
    volume_element.inner_text = AsyncMock(return_value="100K+")

    row = Mock()
    row.query_selector = AsyncMock(
        side_effect=lambda selector: {
            ".mZ3RIc": title_element,
            ".lqv0Cb": volume_element,
        }[selector]
    )
    row.click = AsyncMock()

    first_news_title = Mock()
    first_news_title.count = AsyncMock(return_value=1)
    first_news_title.inner_text = AsyncMock(return_value="Primary headline")
    title_matches = Mock()
    title_matches.first = first_news_title

    first_news_link = Mock()
    first_news_link.count = AsyncMock(return_value=1)
    first_news_link.get_attribute = AsyncMock(
        return_value="https://example.test/primary"
    )
    link_matches = Mock()
    link_matches.first = first_news_link

    news = Mock()
    news.locator = Mock(
        side_effect=lambda selector: {
            ".QbLC8c": title_matches,
            "a": link_matches,
        }[selector]
    )
    analysis_locator = Mock()
    analysis_locator.all_inner_texts = AsyncMock(return_value=["Analysis"])
    news_locator = Mock()
    news_locator.all = AsyncMock(return_value=[news])

    detail_panel = Mock()
    detail_panel.wait_for = AsyncMock()
    detail_panel.locator = Mock(
        side_effect=lambda selector: (
            analysis_locator
            if selector.startswith("span[")
            else news_locator
        )
    )
    panels = Mock()
    panels.filter.return_value = detail_panel

    page = Mock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[row])
    page.query_selector = AsyncMock(return_value=None)
    page.locator.return_value = panels
    page.get_by_role.return_value = Mock()

    result = asyncio.run(crawl(page, Mock(), None))

    assert result == {
        "status": "success",
        "data": [
            {
                "트렌드 제목": "Target Trend",
                "검색량": "100K+",
                "트렌드 분석": ["Analysis"],
                "뉴스 데이터": [
                    {
                        "뉴스 제목": "Primary headline",
                        "URL": "https://example.test/primary",
                    }
                ],
            }
        ],
    }


def test_crawl_propagates_navigation_failure():
    page = Mock()
    page.goto = AsyncMock(side_effect=RuntimeError("browser unavailable"))

    with pytest.raises(RuntimeError, match="browser unavailable"):
        asyncio.run(crawl(page, Mock(), None))


def test_crawl_rejects_total_extraction_failure():
    row = Mock()
    row.query_selector = AsyncMock(return_value=None)

    page = Mock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[row])
    page.query_selector = AsyncMock(return_value=None)

    with pytest.raises(
        RuntimeError,
        match="Failed to extract any of 1 discovered trend rows",
    ):
        asyncio.run(crawl(page, Mock(), None))


def test_crawl_allows_a_valid_empty_page():
    page = Mock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.query_selector = AsyncMock(return_value=None)

    result = asyncio.run(crawl(page, Mock(), None))

    assert result == {"status": "success", "data": []}
