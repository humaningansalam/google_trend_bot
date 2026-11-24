import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

VALID_LOG_LEVELS = frozenset(
    {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
)
MAX_PORT_NUMBER = 65_535


class ScraperBackend(StrEnum):
    LOCAL = "local"
    REMOTE = "remote"


def parse_scraper_backend(value: str) -> ScraperBackend:
    normalized_value = value.strip().lower()
    try:
        return ScraperBackend(normalized_value)
    except ValueError as exc:
        choices = ", ".join(backend.value for backend in ScraperBackend)
        raise ValueError(f"SCRAPER_BACKEND must be one of: {choices}") from exc


def _optional_value(value: str | None) -> str | None:
    if value is None:
        return None
    stripped_value = value.strip()
    return stripped_value or None


def _non_blank_value(
    environment: Mapping[str, str],
    name: str,
    default: str,
) -> str:
    value = environment.get(name, default).strip()
    if not value:
        raise ValueError(f"{name} must not be blank")
    return value


def _log_level(environment: Mapping[str, str]) -> str:
    value = _non_blank_value(environment, "LOG_LEVEL", "INFO").upper()
    if value not in VALID_LOG_LEVELS:
        choices = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ValueError(f"LOG_LEVEL must be one of: {choices}")
    return value


def _positive_integer(
    environment: Mapping[str, str],
    name: str,
    default: int,
) -> int:
    raw_value = environment.get(name, str(default))
    try:
        parsed_value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed_value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return parsed_value


def _port_number(environment: Mapping[str, str]) -> int:
    port_number = _positive_integer(environment, "PORT", 5000)
    if port_number > MAX_PORT_NUMBER:
        raise ValueError("PORT must be between 1 and 65535")
    return port_number


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str
    app_environment: str
    log_level: str
    log_file: str
    slack_webhook: str
    schedule_interval_minutes: int
    control_token: str | None
    scraper_backend: ScraperBackend
    playwright_url: str
    loki_url: str | None
    bind_host: str
    bind_port: int

    @property
    def loki_tags(self) -> dict[str, str]:
        return {"app": self.app_name, "env": self.app_environment}


def load_settings(
    environment: Mapping[str, str] | None = None,
) -> Settings:
    values = os.environ if environment is None else environment

    slack_webhook = _optional_value(values.get("SLACK_WEBHOOK"))
    if slack_webhook is None:
        raise ValueError("SLACK_WEBHOOK is required")

    return Settings(
        app_name=_non_blank_value(values, "APP_NAME", "google-trend-bot"),
        app_environment=_non_blank_value(values, "APP_ENV", "dev"),
        log_level=_log_level(values),
        log_file=_non_blank_value(values, "LOG_FILE", "./logs/bot.log"),
        slack_webhook=slack_webhook,
        schedule_interval_minutes=_positive_integer(
            values,
            "SCHEDULE_INTERVAL",
            10,
        ),
        control_token=_optional_value(values.get("CONTROL_TOKEN")),
        scraper_backend=parse_scraper_backend(
            values.get("SCRAPER_BACKEND", ScraperBackend.LOCAL.value)
        ),
        playwright_url=_non_blank_value(
            values,
            "PLAYWRIGHT_URL",
            "http://localhost:3000",
        ),
        loki_url=_optional_value(values.get("LOKI_URL")),
        bind_host=_non_blank_value(values, "BIND_HOST", "127.0.0.1"),
        bind_port=_port_number(values),
    )
