from unittest.mock import Mock

def test_scraper_initialization(test_scraper):
    assert test_scraper.chrome_options is not None
    assert "--headless" in test_scraper.chrome_options.arguments
    assert "--disable-gpu" in test_scraper.chrome_options.arguments

def test_scraper_setup_driver(test_scraper, mock_webdriver):
    driver = test_scraper.setup_driver()
    assert driver is not None

def test_scrape_trends(test_scraper, mock_webdriver):
    data = test_scraper.scrape_trends()
    assert isinstance(data, list)

def test_extract_trend_data(test_scraper, mock_webdriver):
    mock_tr = Mock()
    mock_driver = Mock()
    
    # Mock the required elements
    mock_tr.find_element.return_value.text = "Test Trend"
    mock_driver.find_element.return_value.find_elements.return_value = []
    
    data = test_scraper._extract_trend_data(mock_tr, mock_driver)
    assert isinstance(data, dict)
    assert "트렌드 제목" in data
    assert data["트렌드 제목"] == "Test Trend"