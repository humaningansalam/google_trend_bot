from flask import Flask, Response, jsonify, request
from prometheus_client import generate_latest
from werkzeug.exceptions import HTTPException

from his_mon import ResourceMonitor, setup_logging

from src.bot.rss_bot import RSSBot
from src.bot.scraper import Scraper
from src.common.api_contracts import (
    ApiErrorCode,
    BotState,
    error_response,
    scrape_error_response,
    success_response,
)
from src.common.metrics import metrics
from src.common.rss_parser import RSSParser
from src.common.scrape_contracts import ScrapeResult
from src.config import Config


def create_app(bot=None, scraper=None):
    app = Flask(__name__)
    app.bot = bot
    app.scraper = scraper

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        error_codes = {
            404: ApiErrorCode.NOT_FOUND,
            405: ApiErrorCode.METHOD_NOT_ALLOWED,
        }
        return error_response(
            error_codes.get(error.code, ApiErrorCode.HTTP_ERROR),
            error.description,
            error.code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled request error", exc_info=error)
        return error_response(
            ApiErrorCode.INTERNAL_ERROR, "Internal server error", 500
        )

    def authorize_control_request():
        control_token = Config.CONTROL_TOKEN
        if not control_token:
            return None
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {control_token}":
            return error_response(
                ApiErrorCode.UNAUTHORIZED, "Unauthorized", 401
            )
        return None

    @app.route("/start", methods=["POST"])
    def start_bot():
        unauthorized = authorize_control_request()
        if unauthorized:
            return unauthorized
        if not app.bot:
            return error_response(
                ApiErrorCode.BOT_NOT_INITIALIZED, "Bot not initialized", 400
            )
        if app.bot.start():
            return success_response(state=BotState.RUNNING.value)
        return error_response(
            ApiErrorCode.BOT_ALREADY_RUNNING,
            "Bot is already running",
            400,
        )

    @app.route("/stop", methods=["POST"])
    def stop_bot():
        unauthorized = authorize_control_request()
        if unauthorized:
            return unauthorized
        if not app.bot:
            return error_response(
                ApiErrorCode.BOT_NOT_INITIALIZED, "Bot not initialized", 400
            )
        stopped = app.bot.stop()
        if stopped:
            return success_response(state=BotState.STOPPED.value)
        return success_response(state=BotState.STOPPING.value)

    @app.route("/reset", methods=["POST"])
    def reset_trend():
        unauthorized = authorize_control_request()
        if unauthorized:
            return unauthorized
        if not app.bot:
            return error_response(
                ApiErrorCode.BOT_NOT_INITIALIZED, "Bot not initialized", 400
            )
        app.bot.reset_trend()
        return success_response()

    @app.route("/trends", methods=["GET"])
    async def get_trends():
        if not app.scraper:
            return error_response(
                ApiErrorCode.SCRAPER_NOT_INITIALIZED,
                "Scraper not initialized",
                400,
            )
        try:
            result = await app.scraper.scrape_trends()
        except Exception:
            app.logger.exception("Trend scraping failed")
            return scrape_error_response(
                ApiErrorCode.SCRAPER_CONTRACT_VIOLATION,
                "Failed to fetch trends",
            )
        if not isinstance(result, ScrapeResult):
            app.logger.error(
                "Trend scraper violated its result contract: %s",
                type(result).__name__,
            )
            return scrape_error_response(
                ApiErrorCode.SCRAPER_CONTRACT_VIOLATION,
                "Failed to fetch trends",
            )
        if result.is_success:
            return success_response(data=result.data)
        app.logger.warning(
            "Trend scraper failed: code=%s message=%s",
            result.error.code.value,
            result.error.message,
        )
        return scrape_error_response(result.error.code, result.error.message)

    @app.route("/metrics")
    def metrics_endpoint():
        return Response(generate_latest(), mimetype="text/plain")

    @app.route("/health")
    def health():
        return "Healthy"

    return app


def create_runtime_app():
    setup_logging(
        level=Config.LOG_LEVEL,
        loki_url=Config.LOKI_URL,
        tags=Config.LOKI_TAGS,
        log_file=Config.LOG_FILE,
    )

    rss_parser = RSSParser()
    bot = RSSBot(
        rss_parser,
        interval=Config.SCHEDULE_INTERVAL,
        webhook_url=Config.SLACK_WEBHOOK,
    )
    scraper = Scraper(backend=Config.SCRAPER_BACKEND)

    app = create_app(bot=bot, scraper=scraper)

    monitor = ResourceMonitor(metrics_obj=metrics, interval=5)
    monitor.start()
    app.extensions["resource_monitor"] = monitor

    bot.start()
    return app


def main():
    app = create_runtime_app()
    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
