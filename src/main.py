import hmac
from typing import cast

from flask import Flask, Response, current_app, request
from his_mon import ResourceMonitor, setup_logging
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from werkzeug.exceptions import HTTPException

from src.bot.scraper import GoogleTrendsScraper
from src.bot.trend_alert_bot import TrendAlertBot
from src.clients.playwright_submit import PlaywrightJobClient
from src.common.api_contracts import (
    ApiErrorCode,
    ApiResponse,
    BotState,
    error_response,
    success_response,
    upstream_error_response,
)
from src.common.metrics import metrics
from src.common.rss_parser import RSSParser
from src.common.scrape_contracts import ScrapeResult
from src.config import ScraperBackend, Settings, load_settings

BOT_EXTENSION_KEY = "trend_alert_bot"
SCRAPER_EXTENSION_KEY = "google_trends_scraper"
OPERATOR_AUTH_EXTENSION_KEY = "operator_auth"
RESOURCE_MONITOR_EXTENSION_KEY = "resource_monitor"
RESOURCE_MONITOR_INTERVAL_SECONDS = 5
HTTP_ERROR_CODES = {
    404: ApiErrorCode.NOT_FOUND,
    405: ApiErrorCode.METHOD_NOT_ALLOWED,
}


def create_app(
    trend_alert_bot: TrendAlertBot | None = None,
    trend_scraper: GoogleTrendsScraper | None = None,
    control_token: str | None = None,
) -> Flask:
    app = Flask(__name__)
    app.extensions[BOT_EXTENSION_KEY] = trend_alert_bot
    app.extensions[SCRAPER_EXTENSION_KEY] = trend_scraper
    app.extensions[OPERATOR_AUTH_EXTENSION_KEY] = control_token
    _register_error_handlers(app)
    _register_routes(app)
    return app


def _register_error_handlers(app: Flask) -> None:
    app.register_error_handler(HTTPException, _handle_http_error)
    app.register_error_handler(Exception, _handle_unexpected_error)


def _register_routes(app: Flask) -> None:
    app.add_url_rule(
        "/start", endpoint="start_bot", view_func=_start_bot, methods=["POST"]
    )
    app.add_url_rule(
        "/stop", endpoint="stop_bot", view_func=_stop_bot, methods=["POST"]
    )
    app.add_url_rule(
        "/reset",
        endpoint="reset_trend_memory",
        view_func=_reset_trend_memory,
        methods=["POST"],
    )
    app.add_url_rule(
        "/trends", endpoint="get_trends", view_func=_get_trends, methods=["GET"]
    )
    app.add_url_rule(
        "/metrics",
        endpoint="metrics_endpoint",
        view_func=_metrics_endpoint,
        methods=["GET"],
    )
    app.add_url_rule("/health", endpoint="health", view_func=_health, methods=["GET"])


def _handle_http_error(error: HTTPException) -> ApiResponse:
    status_code = error.code or 500
    return error_response(
        HTTP_ERROR_CODES.get(status_code, ApiErrorCode.HTTP_ERROR),
        error.description,
        status_code,
    )


def _handle_unexpected_error(error: Exception) -> ApiResponse:
    current_app.logger.exception(
        "Unhandled request error: %s",
        type(error).__name__,
    )
    return error_response(
        ApiErrorCode.INTERNAL_ERROR,
        "Internal server error",
        500,
    )


def _authorize_control_request() -> ApiResponse | None:
    control_token = cast(
        str | None,
        current_app.extensions[OPERATOR_AUTH_EXTENSION_KEY],
    )
    if control_token is None:
        return None

    provided_authorization = request.headers.get("Authorization", "")
    expected_authorization = f"Bearer {control_token}"
    if hmac.compare_digest(provided_authorization, expected_authorization):
        return None
    return error_response(
        ApiErrorCode.UNAUTHORIZED,
        "Unauthorized",
        401,
    )


def _get_trend_alert_bot() -> TrendAlertBot | None:
    return cast(
        TrendAlertBot | None,
        current_app.extensions[BOT_EXTENSION_KEY],
    )


def _get_google_trends_scraper() -> GoogleTrendsScraper | None:
    return cast(
        GoogleTrendsScraper | None,
        current_app.extensions[SCRAPER_EXTENSION_KEY],
    )


def _start_bot() -> ApiResponse:
    unauthorized_response = _authorize_control_request()
    if unauthorized_response is not None:
        return unauthorized_response

    bot = _get_trend_alert_bot()
    if bot is None:
        return error_response(
            ApiErrorCode.BOT_NOT_INITIALIZED,
            "Bot not initialized",
            400,
        )
    if bot.start():
        return success_response(state=BotState.RUNNING.value)
    return error_response(
        ApiErrorCode.BOT_ALREADY_RUNNING,
        "Bot is already running",
        400,
    )


def _stop_bot() -> ApiResponse:
    unauthorized_response = _authorize_control_request()
    if unauthorized_response is not None:
        return unauthorized_response

    bot = _get_trend_alert_bot()
    if bot is None:
        return error_response(
            ApiErrorCode.BOT_NOT_INITIALIZED,
            "Bot not initialized",
            400,
        )
    state = BotState.STOPPED if bot.stop() else BotState.STOPPING
    return success_response(state=state.value)


def _reset_trend_memory() -> ApiResponse:
    unauthorized_response = _authorize_control_request()
    if unauthorized_response is not None:
        return unauthorized_response

    bot = _get_trend_alert_bot()
    if bot is None:
        return error_response(
            ApiErrorCode.BOT_NOT_INITIALIZED,
            "Bot not initialized",
            400,
        )
    bot.prune_seen_trends()
    return success_response()


async def _get_trends() -> ApiResponse:
    scraper = _get_google_trends_scraper()
    if scraper is None:
        return error_response(
            ApiErrorCode.SCRAPER_NOT_INITIALIZED,
            "Scraper not initialized",
            400,
        )
    try:
        result = await scraper.scrape_trends()
    except Exception:
        current_app.logger.exception("Trend scraping failed")
        return upstream_error_response(
            ApiErrorCode.SCRAPER_CONTRACT_VIOLATION,
            "Failed to fetch trends",
        )

    if not isinstance(result, ScrapeResult):
        current_app.logger.error(
            "Trend scraper violated its result contract: %s",
            type(result).__name__,
        )
        return upstream_error_response(
            ApiErrorCode.SCRAPER_CONTRACT_VIOLATION,
            "Failed to fetch trends",
        )
    if result.is_success:
        return success_response(data=result.data)

    scrape_error = result.error
    if scrape_error is None:
        raise AssertionError("Failed scrape result is missing its error")
    current_app.logger.warning(
        "Trend scraper failed: code=%s message=%s",
        scrape_error.code.value,
        scrape_error.message,
    )
    return upstream_error_response(
        scrape_error.code,
        scrape_error.message,
    )


def _metrics_endpoint() -> Response:
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)


def _health() -> Response:
    bot = _get_trend_alert_bot()
    response = current_app.make_response("Healthy")
    response.headers["X-Bot-Active"] = (
        "true" if bot is not None and bot.is_active() else "false"
    )
    return response


def create_runtime_app(settings: Settings | None = None) -> Flask:
    runtime_settings = settings or load_settings()
    setup_logging(
        level=runtime_settings.log_level,
        loki_url=runtime_settings.loki_url,
        tags=runtime_settings.loki_tags,
        log_file=runtime_settings.log_file,
    )

    trend_alert_bot = TrendAlertBot(
        RSSParser(),
        poll_interval_minutes=runtime_settings.schedule_interval_minutes,
        webhook_url=runtime_settings.slack_webhook,
    )
    job_client = (
        PlaywrightJobClient(server_url=runtime_settings.playwright_url)
        if runtime_settings.scraper_backend is ScraperBackend.REMOTE
        else None
    )
    trend_scraper = GoogleTrendsScraper(
        backend=runtime_settings.scraper_backend,
        job_client=job_client,
    )
    app = create_app(
        trend_alert_bot=trend_alert_bot,
        trend_scraper=trend_scraper,
        control_token=runtime_settings.control_token,
    )

    if not trend_alert_bot.start():
        raise RuntimeError("Trend alert worker did not start")

    resource_monitor = ResourceMonitor(
        metrics_obj=metrics,
        interval=RESOURCE_MONITOR_INTERVAL_SECONDS,
    )
    try:
        resource_monitor.start()
    except Exception:
        trend_alert_bot.stop()
        raise
    app.extensions[RESOURCE_MONITOR_EXTENSION_KEY] = resource_monitor

    if runtime_settings.control_token is None:
        app.logger.warning(
            "CONTROL_TOKEN is unset; control endpoints require a trusted network"
        )
    return app


def main() -> None:
    settings = load_settings()
    app = create_runtime_app(settings)
    app.run(host=settings.bind_host, port=settings.bind_port)


if __name__ == "__main__":
    main()
