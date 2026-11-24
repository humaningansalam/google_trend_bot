import pytest

from src.config import ScraperBackend, load_settings

REQUIRED_ENVIRONMENT = {
    "SLACK_WEBHOOK": "https://hooks.slack.test/services/example",
}


def test_settings_use_documented_defaults():
    settings = load_settings(REQUIRED_ENVIRONMENT)

    assert settings.app_name == "google-trend-bot"
    assert settings.app_environment == "dev"
    assert settings.log_level == "INFO"
    assert settings.schedule_interval_minutes == 10
    assert settings.control_token is None
    assert settings.loki_url is None
    assert settings.scraper_backend is ScraperBackend.LOCAL
    assert settings.playwright_url == "http://localhost:3000"
    assert settings.bind_host == "127.0.0.1"
    assert settings.bind_port == 5000
    assert settings.loki_tags == {"app": "google-trend-bot", "env": "dev"}


@pytest.mark.parametrize("value", ["not-a-number", "0", "-1"])
def test_schedule_interval_must_be_a_positive_integer(value: str):
    environment = {**REQUIRED_ENVIRONMENT, "SCHEDULE_INTERVAL": value}

    with pytest.raises(ValueError, match=r"SCHEDULE_INTERVAL.*positive integer"):
        load_settings(environment)


@pytest.mark.parametrize("value", ["not-a-number", "0", "-1"])
def test_port_must_be_a_positive_integer(value: str):
    environment = {**REQUIRED_ENVIRONMENT, "PORT": value}

    with pytest.raises(ValueError, match=r"PORT.*positive integer"):
        load_settings(environment)


def test_port_must_fit_the_tcp_port_range():
    environment = {**REQUIRED_ENVIRONMENT, "PORT": "65536"}

    with pytest.raises(ValueError, match="between 1 and 65535"):
        load_settings(environment)


@pytest.mark.parametrize(
    "name",
    ["APP_NAME", "APP_ENV", "LOG_FILE", "PLAYWRIGHT_URL", "BIND_HOST"],
)
def test_text_settings_must_not_be_blank(name: str):
    environment = {**REQUIRED_ENVIRONMENT, name: "   "}

    with pytest.raises(ValueError, match=rf"{name} must not be blank"):
        load_settings(environment)


def test_log_level_must_be_recognized():
    environment = {**REQUIRED_ENVIRONMENT, "LOG_LEVEL": "verbose"}

    with pytest.raises(ValueError, match="LOG_LEVEL must be one of"):
        load_settings(environment)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("local", ScraperBackend.LOCAL),
        ("REMOTE", ScraperBackend.REMOTE),
    ],
)
def test_scraper_backend_is_explicit(value: str, expected: ScraperBackend):
    environment = {**REQUIRED_ENVIRONMENT, "SCRAPER_BACKEND": value}

    assert load_settings(environment).scraper_backend is expected


def test_unknown_scraper_backend_is_rejected():
    environment = {**REQUIRED_ENVIRONMENT, "SCRAPER_BACKEND": "sometimes"}

    with pytest.raises(ValueError, match="SCRAPER_BACKEND must be one of"):
        load_settings(environment)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_slack_webhook_is_required(value: str | None):
    environment = {} if value is None else {"SLACK_WEBHOOK": value}

    with pytest.raises(ValueError, match="SLACK_WEBHOOK is required"):
        load_settings(environment)


def test_blank_optional_values_are_normalized_to_none():
    settings = load_settings(
        {
            **REQUIRED_ENVIRONMENT,
            "CONTROL_TOKEN": " ",
            "LOKI_URL": "",
        }
    )

    assert settings.control_token is None
    assert settings.loki_url is None
