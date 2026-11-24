from unittest.mock import Mock, patch

import pytest

from src.common.rss_parser import RSSParser, TrendEntry


def parse_payload(payload: bytes) -> list[TrendEntry]:
    response = Mock(content=payload)
    response.raise_for_status.return_value = None

    with patch("src.common.rss_parser.requests.get", return_value=response):
        return RSSParser().parse("https://example.test/trends.xml")


def test_parser_returns_typed_entries_for_a_valid_feed():
    result = parse_payload(
        b"""
        <rss version="2.0">
          <channel>
            <item>
              <title>  Sample Trend  </title>
              <description>  Sample summary  </description>
              <link>  https://example.test/sample  </link>
              <pubDate>Tue, 24 Nov 2026 00:00:00 GMT</pubDate>
            </item>
          </channel>
        </rss>
        """
    )

    assert len(result) == 1
    assert result[0].title == "Sample Trend"
    assert result[0].content == "Sample summary"
    assert result[0].link == "https://example.test/sample"
    assert result[0].published == "Tue, 24 Nov 2026 00:00:00 GMT"
    assert result[0].observed_at.tzinfo is not None


def test_parser_rejects_non_feed_content():
    with pytest.raises(ValueError, match="not a recognized feed"):
        parse_payload(b"<html>rate limited</html>")


def test_parser_rejects_malformed_rss():
    with pytest.raises(ValueError, match="malformed"):
        parse_payload(b'<rss version="2.0"><channel>')


def test_parser_rejects_an_entry_missing_required_fields():
    payload = b"""
    <rss version="2.0">
      <channel><item><title>Incomplete</title></item></channel>
    </rss>
    """

    with pytest.raises(ValueError, match="missing required field"):
        parse_payload(payload)


def test_parser_allows_a_valid_empty_feed():
    result = parse_payload(b'<rss version="2.0"><channel></channel></rss>')

    assert result == []
