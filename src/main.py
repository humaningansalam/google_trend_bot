from flask import Flask, Response, jsonify, request
from prometheus_client import generate_latest
from werkzeug.exceptions import HTTPException

from his_mon import ResourceMonitor, init_webhook, setup_logging

from src.bot.rss_bot import RSSBot
from src.bot.scraper import Scraper
from src.common.metrics import metrics
from src.common.rss_parser import RSSParser
from src.config import Config


def create_app(bot=None, scraper=None):
    app = Flask(__name__)
    app.bot = bot
    app.scraper = scraper

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify({"status": "error", "message": error.description}), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled request error", exc_info=error)
        return jsonify({"status": "error", "message": "Internal server error"}), 500

    def authorize_control_request():
        control_token = Config.CONTROL_TOKEN
        if not control_token:
            return None
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {control_token}":
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        return None

    @app.route("/start", methods=["POST"])
    def start_bot():
        unauthorized = authorize_control_request()
        if unauthorized:
            return unauthorized
        if not app.bot:
            return jsonify({"status": "error", "message": "Bot not initialized"}), 400
        if app.bot.start():
            return jsonify({"status": "Bot started"}), 200
        return jsonify({"status": "error", "message": "Bot is already running"}), 400

    @app.route("/stop", methods=["POST"])
    def stop_bot():
        unauthorized = authorize_control_request()
        if unauthorized:
            return unauthorized
        if not app.bot:
            return jsonify({"status": "error", "message": "Bot not initialized"}), 400
        stopped = app.bot.stop()
        if stopped:
            return jsonify({"status": "Bot stopped", "state": "stopped"}), 200
        return jsonify({"status": "Bot stop timed out", "state": "stopping"}), 200

    @app.route("/reset", methods=["POST"])
    def reset_trend():
        unauthorized = authorize_control_request()
        if unauthorized:
            return unauthorized
        if not app.bot:
            return jsonify({"status": "error", "message": "Bot not initialized"}), 400
        app.bot.reset_trend()
        return jsonify({"status": "Trend reset completed"}), 200

    @app.route("/trends", methods=["GET"])
    async def get_trends():
        if not app.scraper:
            return jsonify({"status": "error", "message": "Scraper not initialized"}), 400
        try:
            result = app.scraper.scrape_trends()
            if hasattr(result, "__await__"):
                result = await result
        except Exception:
            app.logger.exception("Trend scraping failed")
            return jsonify({"status": "error", "message": "Failed to fetch trends"}), 502
        if not isinstance(result, dict):
            app.logger.error(
                "Trend scraper returned invalid result type: %s",
                type(result).__name__,
            )
            return jsonify({"status": "error", "message": "Failed to fetch trends"}), 502
        if result.get("status") == "success" and "data" in result:
            return jsonify({"status": "success", "data": result["data"]}), 200
        if result.get("status") == "error" and isinstance(result.get("message"), str):
            app.logger.warning(
                "Trend scraper reported failure: %s", result["message"]
            )
            return jsonify({"status": "error", "message": result["message"]}), 502
        app.logger.error(
            "Trend scraper returned malformed payload: status=%r keys=%s",
            result.get("status"),
            sorted(str(key) for key in result),
        )
        return jsonify({"status": "error", "message": "Failed to fetch trends"}), 502

    @app.route("/metrics")
    def metrics_endpoint():
        return Response(generate_latest(), mimetype="text/plain")

    @app.route("/health")
    def health():
        return "Healthy"

    return app


def create_runtime_app():
    init_webhook(url=Config.SLACK_WEBHOOK)
    setup_logging(
        level=Config.LOG_LEVEL,
        loki_url=Config.LOKI_URL,
        tags=Config.LOKI_TAGS,
        log_file=Config.LOG_FILE,
    )

    rss_parser = RSSParser()
    bot = RSSBot(rss_parser, interval=Config.SCHEDULE_INTERVAL)
    scraper = Scraper()

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
