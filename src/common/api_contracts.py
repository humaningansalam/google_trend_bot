from enum import Enum

from flask import jsonify

from src.common.scrape_contracts import ScrapeErrorCode


class ApiErrorCode(str, Enum):
    UNAUTHORIZED = "unauthorized"
    BOT_NOT_INITIALIZED = "bot_not_initialized"
    BOT_ALREADY_RUNNING = "bot_already_running"
    SCRAPER_NOT_INITIALIZED = "scraper_not_initialized"
    SCRAPER_CONTRACT_VIOLATION = "scraper_contract_violation"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    HTTP_ERROR = "http_error"
    INTERNAL_ERROR = "internal_error"


class BotState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    STOPPING = "stopping"


def success_response(http_status: int = 200, **payload):
    return jsonify({"status": "success", **payload}), http_status


def error_response(
    code: ApiErrorCode | ScrapeErrorCode,
    message: str,
    http_status: int,
):
    return (
        jsonify({"status": "error", "code": code.value, "message": message}),
        http_status,
    )


def scrape_error_response(
    code: ApiErrorCode | ScrapeErrorCode,
    message: str,
):
    return error_response(code, message, 502)
