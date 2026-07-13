from unittest.mock import Mock, patch

import pytest

from src.common.rss_parser import RSSParser


def parse_payload(payload):
    response = Mock(content=payload)
    response.raise_for_status.return_value = None

    with patch("src.common.rss_parser.requests.get", return_value=response):
        return RSSParser().parse("https://example.test/trends.xml")


def test_rss_parser_rejects_non_feed_content():
    with pytest.raises(ValueError, match="not a recognized feed"):
        parse_payload(b"<html>rate limited</html>")


def test_rss_parser_rejects_malformed_rss():
    with pytest.raises(ValueError, match="malformed"):
        parse_payload(b'<rss version="2.0"><channel>')


def test_rss_parser_allows_a_valid_empty_feed():
    result = parse_payload(
        b'<rss version="2.0"><channel></channel></rss>'
    )

    assert result == []
