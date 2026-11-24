from enum import StrEnum

from flask import Response, jsonify

from src.common.scrape_contracts import ScrapeErrorCode


class ApiErrorCode(StrEnum):
    UNAUTHORIZED = "unauthorized"
    BOT_NOT_INITIALIZED = "bot_not_initialized"
    BOT_ALREADY_RUNNING = "bot_already_running"
    SCRAPER_NOT_INITIALIZED = "scraper_not_initialized"
    SCRAPER_CONTRACT_VIOLATION = "scraper_contract_violation"
    NOT_FOUND = "not_found"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    HTTP_ERROR = "http_error"
    INTERNAL_ERROR = "internal_error"


class BotState(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    STOPPING = "stopping"


ApiResponse = tuple[Response, int]


def success_response(http_status: int = 200, **payload: object) -> ApiResponse:
    return jsonify({"status": "success", **payload}), http_status


def error_response(
    code: ApiErrorCode | ScrapeErrorCode,
    message: str,
    http_status: int,
) -> ApiResponse:
    return (
        jsonify({"status": "error", "code": code.value, "message": message}),
        http_status,
    )


def upstream_error_response(
    code: ApiErrorCode | ScrapeErrorCode,
    message: str,
) -> ApiResponse:
    return error_response(code, message, 502)
