import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.crawl_scripts.google_trends_crawl import (
    _extract_trend_data,
    _open_detail_panel,
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
