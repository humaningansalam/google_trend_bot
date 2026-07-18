import os
from enum import Enum


class ScraperBackend(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"


def parse_scraper_backend(value: str) -> ScraperBackend:
    normalized = value.strip().lower()
    if normalized == "false":
        return ScraperBackend.LOCAL
    if normalized == "true":
        return ScraperBackend.REMOTE
    raise ValueError("USE_SERVER must be either True or False")


class Config:
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")

    schedule_interval = os.getenv("SCHEDULE_INTERVAL", "10")
    try:
        SCHEDULE_INTERVAL = int(schedule_interval)
    except ValueError as exc:
        raise ValueError("SCHEDULE_INTERVAL must be a positive integer") from exc
    if SCHEDULE_INTERVAL <= 0:
        raise ValueError("SCHEDULE_INTERVAL must be a positive integer")

    CONTROL_TOKEN = os.getenv("CONTROL_TOKEN")
    SCRAPER_BACKEND = parse_scraper_backend(os.getenv("USE_SERVER", "False"))
    LOKI_URL = os.getenv("LOKI_URL")
    LOKI_TAGS = {
        "app": os.getenv("APP_NAME", "google-trend-bot"),
        "env": os.getenv("APP_ENV", "dev"),
    }
    LOG_FILE = "./logs/bot.log"
