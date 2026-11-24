from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from src.bot.scraper import GoogleTrendsScraper
from src.bot.trend_alert_bot import TrendAlertBot
from src.clients.playwright_submit import PlaywrightJobClient
from src.common.api_contracts import ApiErrorCode, BotState
from src.common.scrape_contracts import ScrapeErrorCode, ScrapeResult
from src.config import ScraperBackend, Settings
from src.main import (
    BOT_EXTENSION_KEY,
    RESOURCE_MONITOR_EXTENSION_KEY,
    SCRAPER_EXTENSION_KEY,
    create_app,
    create_runtime_app,
)

CONTROL_TOKEN = "secret-token"


def test_health_reports_http_and_worker_liveness(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data == b"Healthy"
    assert response.headers["X-Bot-Active"] == "false"

    client.post("/start")
    assert client.get("/health").headers["X-Bot-Active"] == "true"

    client.post("/stop")
    assert client.get("/health").headers["X-Bot-Active"] == "false"


def test_start_returns_running_state(client):
    response = client.post("/start")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "success",
        "state": BotState.RUNNING.value,
    }


def test_second_start_returns_a_stable_error(client):
    client.post("/start")

    response = client.post("/start")

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "code": ApiErrorCode.BOT_ALREADY_RUNNING.value,
        "message": "Bot is already running",
    }


@pytest.mark.parametrize("path", ["/start", "/stop", "/reset"])
@pytest.mark.parametrize("authorization", [None, "Bearer wrong-token"])
def test_control_endpoints_reject_missing_or_wrong_tokens(
    path: str,
    authorization: str | None,
    trend_bot: TrendAlertBot,
    trend_scraper: GoogleTrendsScraper,
):
    app = create_app(
        trend_alert_bot=trend_bot,
        trend_scraper=trend_scraper,
        control_token=CONTROL_TOKEN,
    )
    headers = {} if authorization is None else {"Authorization": authorization}

    response = app.test_client().post(path, headers=headers)

    assert response.status_code == 401
    assert response.get_json() == {
        "status": "error",
        "code": ApiErrorCode.UNAUTHORIZED.value,
        "message": "Unauthorized",
    }


@pytest.mark.parametrize("path", ["/start", "/stop", "/reset"])
def test_control_endpoints_accept_the_configured_token(
    path: str,
    trend_bot: TrendAlertBot,
    trend_scraper: GoogleTrendsScraper,
):
    app = create_app(
        trend_alert_bot=trend_bot,
        trend_scraper=trend_scraper,
        control_token=CONTROL_TOKEN,
    )

    response = app.test_client().post(
        path,
        headers={"Authorization": f"Bearer {CONTROL_TOKEN}"},
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "success"


def test_stop_is_idempotent(client):
    response = client.post("/stop")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "success",
        "state": BotState.STOPPED.value,
    }


def test_stop_reports_when_the_worker_is_still_stopping(
    client,
    trend_bot: TrendAlertBot,
):
    trend_bot.stop = Mock(return_value=False)

    response = client.post("/stop")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "success",
        "state": BotState.STOPPING.value,
    }


@pytest.mark.parametrize("path", ["/health", "/metrics", "/trends"])
def test_read_only_endpoints_remain_open_when_control_token_is_set(
    path: str,
    trend_bot: TrendAlertBot,
    trend_scraper: GoogleTrendsScraper,
):
    app = create_app(
        trend_alert_bot=trend_bot,
        trend_scraper=trend_scraper,
        control_token=CONTROL_TOKEN,
    )

    response = app.test_client().get(path)

    assert response.status_code == 200


def test_trends_returns_the_scraper_data(client):
    response = client.get("/trends")

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "success",
        "data": [{"trend": "Test Trend"}],
    }


def test_trends_preserves_typed_scraper_errors(client, trend_scraper):
    trend_scraper.scrape_trends = AsyncMock(
        return_value=ScrapeResult.failure(
            ScrapeErrorCode.CRAWL_FAILED,
            "crawl failed",
        )
    )

    response = client.get("/trends")

    assert response.status_code == 502
    assert response.get_json() == {
        "status": "error",
        "code": ScrapeErrorCode.CRAWL_FAILED.value,
        "message": "crawl failed",
    }


def test_trends_does_not_expose_credentials_from_a_remote_url(
    client,
    monkeypatch: pytest.MonkeyPatch,
):
    secret = "REMOTE_SUPERSECRET"
    server_url = f"http://user:{secret}@playwright-server"
    failed_response = requests.Response()
    failed_response.status_code = 500
    failed_response.url = f"{server_url}/api/jobs/submit"
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=failed_response),
    )
    client.application.extensions[SCRAPER_EXTENSION_KEY] = GoogleTrendsScraper(
        backend=ScraperBackend.REMOTE,
        job_client=PlaywrightJobClient(server_url=server_url),
    )

    response = client.get("/trends")

    assert response.status_code == 502
    assert response.get_json() == {
        "status": "error",
        "code": ScrapeErrorCode.REMOTE_SUBMISSION_FAILED.value,
        "message": "Remote job submission failed with HTTP 500",
    }
    assert secret not in response.get_data(as_text=True)


def test_trends_converts_an_unexpected_exception_to_json(client, trend_scraper):
    trend_scraper.scrape_trends = AsyncMock(
        side_effect=RuntimeError("unexpected implementation detail")
    )

    response = client.get("/trends")

    assert response.status_code == 502
    assert response.get_json() == {
        "status": "error",
        "code": ApiErrorCode.SCRAPER_CONTRACT_VIOLATION.value,
        "message": "Failed to fetch trends",
    }


def test_trends_rejects_a_non_contract_result(client, trend_scraper):
    trend_scraper.scrape_trends = AsyncMock(return_value={"status": "success"})

    response = client.get("/trends")

    assert response.status_code == 502
    assert response.get_json() == {
        "status": "error",
        "code": ApiErrorCode.SCRAPER_CONTRACT_VIOLATION.value,
        "message": "Failed to fetch trends",
    }


@pytest.mark.parametrize("path", ["/start", "/missing"])
def test_routing_errors_use_the_json_error_contract(client, path: str):
    response = client.get(path)

    assert response.status_code in {404, 405}
    assert response.mimetype == "application/json"
    assert response.get_json()["status"] == "error"
    assert response.get_json()["code"] in {
        ApiErrorCode.NOT_FOUND.value,
        ApiErrorCode.METHOD_NOT_ALLOWED.value,
    }


@pytest.mark.parametrize("path", ["/start", "/stop", "/reset"])
def test_uninitialized_control_endpoints_use_the_json_error_contract(path: str):
    response = create_app().test_client().post(path)

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "error",
        "code": ApiErrorCode.BOT_NOT_INITIALIZED.value,
        "message": "Bot not initialized",
    }


def test_unhandled_endpoint_exception_uses_the_json_error_contract():
    app = create_app()

    @app.get("/_test-boom")
    def boom():
        raise RuntimeError("boom")

    response = app.test_client().get("/_test-boom")

    assert response.status_code == 500
    assert response.get_json() == {
        "status": "error",
        "code": ApiErrorCode.INTERNAL_ERROR.value,
        "message": "Internal server error",
    }


def test_runtime_factory_wires_explicit_settings_and_starts_services():
    settings = Settings(
        app_name="google-trend-bot",
        app_environment="test",
        log_level="INFO",
        log_file="./logs/test.log",
        slack_webhook="https://hooks.slack.test/services/example",
        schedule_interval_minutes=3,
        control_token=CONTROL_TOKEN,
        scraper_backend=ScraperBackend.REMOTE,
        playwright_url="http://playwright-server:3000",
        loki_url=None,
        bind_host="127.0.0.1",
        bind_port=5000,
    )
    trend_feed = Mock()
    trend_bot = Mock()
    trend_bot.start.return_value = True
    trend_scraper = Mock()
    job_client = Mock()
    resource_monitor = Mock()

    with (
        patch("src.main.setup_logging") as setup_logging,
        patch("src.main.RSSParser", return_value=trend_feed),
        patch("src.main.TrendAlertBot", return_value=trend_bot) as bot_factory,
        patch(
            "src.main.PlaywrightJobClient",
            return_value=job_client,
        ) as job_client_factory,
        patch(
            "src.main.GoogleTrendsScraper",
            return_value=trend_scraper,
        ) as scraper_factory,
        patch(
            "src.main.ResourceMonitor",
            return_value=resource_monitor,
        ) as monitor_factory,
    ):
        app = create_runtime_app(settings)

    setup_logging.assert_called_once_with(
        level="INFO",
        loki_url=None,
        tags={"app": "google-trend-bot", "env": "test"},
        log_file="./logs/test.log",
    )
    bot_factory.assert_called_once_with(
        trend_feed,
        poll_interval_minutes=3,
        webhook_url=settings.slack_webhook,
    )
    job_client_factory.assert_called_once_with(
        server_url="http://playwright-server:3000"
    )
    scraper_factory.assert_called_once_with(
        backend=ScraperBackend.REMOTE,
        job_client=job_client,
    )
    monitor_factory.assert_called_once()
    resource_monitor.start.assert_called_once_with()
    trend_bot.start.assert_called_once_with()
    assert app.extensions[BOT_EXTENSION_KEY] is trend_bot
    assert app.extensions[SCRAPER_EXTENSION_KEY] is trend_scraper
    assert app.extensions[RESOURCE_MONITOR_EXTENSION_KEY] is resource_monitor


def test_runtime_factory_stops_the_worker_when_monitor_startup_fails():
    settings = Settings(
        app_name="google-trend-bot",
        app_environment="test",
        log_level="INFO",
        log_file="./logs/test.log",
        slack_webhook="https://hooks.slack.test/services/example",
        schedule_interval_minutes=3,
        control_token=CONTROL_TOKEN,
        scraper_backend=ScraperBackend.LOCAL,
        playwright_url="http://localhost:3000",
        loki_url=None,
        bind_host="127.0.0.1",
        bind_port=5000,
    )
    trend_bot = Mock()
    trend_bot.start.return_value = True
    resource_monitor = Mock()
    resource_monitor.start.side_effect = RuntimeError("monitor failed")

    with (
        patch("src.main.setup_logging"),
        patch("src.main.RSSParser"),
        patch("src.main.TrendAlertBot", return_value=trend_bot),
        patch("src.main.GoogleTrendsScraper"),
        patch("src.main.ResourceMonitor", return_value=resource_monitor),
        pytest.raises(RuntimeError, match="monitor failed"),
    ):
        create_runtime_app(settings)

    trend_bot.start.assert_called_once_with()
    trend_bot.stop.assert_called_once_with()
