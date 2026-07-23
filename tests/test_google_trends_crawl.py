import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.crawl_scripts.google_trends_crawl import (
    _extract_trend_data,
    _open_detail_panel,
    crawl,
)


def test_open_detail_panel_waits_for_the_clicked_trend_title():
    title_element = Mock()
    title_element.inner_text = AsyncMock(return_value="Target Trend")

    row = Mock()
    row.query_selector = AsyncMock(return_value=title_element)
    row.click = AsyncMock()

    heading = Mock()
    panels = Mock()
    matching_panel = Mock()
    matching_panel.wait_for = AsyncMock()

    page = Mock()
    page.locator.return_value = panels
    page.get_by_role.return_value = heading
    panels.filter.return_value = matching_panel

    result = asyncio.run(_open_detail_panel(page, row))

    row.click.assert_awaited_once_with()
    page.get_by_role.assert_called_once_with(
        "heading", name="Target Trend", exact=True
    )
    panels.filter.assert_called_once_with(has=heading)
    matching_panel.wait_for.assert_awaited_once_with(
        state="visible", timeout=15000
    )
    assert result is matching_panel


def test_open_detail_panel_rejects_a_row_without_a_title():
    row = Mock()
    row.query_selector = AsyncMock(return_value=None)
    row.click = AsyncMock()

    with pytest.raises(ValueError, match="missing a title"):
        asyncio.run(_open_detail_panel(Mock(), row))

    row.click.assert_not_awaited()


def test_extract_trend_data_uses_the_matched_detail_panel():
    title_element = Mock()
    title_element.inner_text = AsyncMock(return_value="Target Trend")
    volume_element = Mock()
    volume_element.inner_text = AsyncMock(return_value="100K+")

    row = Mock()
    row.query_selector = AsyncMock(
        side_effect=[title_element, volume_element]
    )

    analysis_element = Mock()
    analysis_element.inner_text = AsyncMock(return_value="Analysis")
    analysis_locator = Mock()
    analysis_locator.all = AsyncMock(return_value=[analysis_element])
    news_locator = Mock()
    news_locator.all = AsyncMock(return_value=[])
    detail_panel = Mock()
    detail_panel.locator = Mock(
        side_effect=[analysis_locator, news_locator]
    )

    result = asyncio.run(_extract_trend_data(row, detail_panel))

    assert result == {
        "트렌드 제목": "Target Trend",
        "검색량": "100K+",
        "트렌드 분석": ["Analysis"],
        "뉴스 데이터": [],
    }


def test_extract_trend_data_uses_first_news_title_and_link_match():
    title_element = Mock()
    title_element.inner_text = AsyncMock(return_value="Target Trend")
    volume_element = Mock()
    volume_element.inner_text = AsyncMock(return_value="100K+")
    row = Mock()
    row.query_selector = AsyncMock(
        side_effect=[title_element, volume_element]
    )

    first_news_title = Mock()
    first_news_title.count = AsyncMock(return_value=1)
    first_news_title.inner_text = AsyncMock(return_value="Primary headline")
    title_matches = Mock()
    title_matches.first = first_news_title
    title_matches.count = AsyncMock(return_value=2)
    title_matches.inner_text = AsyncMock(
        side_effect=AssertionError("strict multi-match title locator used")
    )

    first_news_link = Mock()
    first_news_link.count = AsyncMock(return_value=1)
    first_news_link.get_attribute = AsyncMock(
        return_value="https://example.test/primary"
    )
    link_matches = Mock()
    link_matches.first = first_news_link
    link_matches.count = AsyncMock(return_value=2)
    link_matches.get_attribute = AsyncMock(
        side_effect=AssertionError("strict multi-match link locator used")
    )

    news = Mock()
    news.locator = Mock(side_effect=[title_matches, link_matches])
    analysis_locator = Mock()
    analysis_locator.all = AsyncMock(return_value=[])
    news_locator = Mock()
    news_locator.all = AsyncMock(return_value=[news])
    detail_panel = Mock()
    detail_panel.locator = Mock(
        side_effect=[analysis_locator, news_locator]
    )

    result = asyncio.run(_extract_trend_data(row, detail_panel))

    assert result["뉴스 데이터"] == [
        {
            "뉴스 제목": "Primary headline",
            "URL": "https://example.test/primary",
        }
    ]


def test_crawl_propagates_navigation_failure():
    page = Mock()
    page.goto = AsyncMock(side_effect=RuntimeError("browser unavailable"))

    with pytest.raises(RuntimeError, match="browser unavailable"):
        asyncio.run(crawl(page, Mock(), None))


def test_crawl_rejects_total_extraction_failure(monkeypatch):
    page = Mock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[Mock()])
    page.query_selector = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "src.crawl_scripts.google_trends_crawl._open_detail_panel",
        AsyncMock(side_effect=RuntimeError("detail selector drift")),
    )

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


def test_crawl_keeps_successful_rows_after_a_partial_extraction_failure(
    monkeypatch,
):
    first_row = Mock()
    second_row = Mock()
    detail_panel = Mock()
    page = Mock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector_all = AsyncMock(
        return_value=[first_row, second_row]
    )
    page.query_selector = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "src.crawl_scripts.google_trends_crawl._open_detail_panel",
        AsyncMock(return_value=detail_panel),
    )
    monkeypatch.setattr(
        "src.crawl_scripts.google_trends_crawl._extract_trend_data",
        AsyncMock(
            side_effect=[
                RuntimeError("first row failed"),
                {"트렌드 제목": "Good Trend"},
            ]
        ),
    )

    result = asyncio.run(crawl(page, Mock(), None))

    assert result == {
        "status": "success",
        "data": [{"트렌드 제목": "Good Trend"}],
    }
