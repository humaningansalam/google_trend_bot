from unittest.mock import Mock, patch

import pytest


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data == b"Healthy"


def test_start_bot(client):
    response = client.post("/start")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "Bot started"


def test_start_bot_returns_json_error_when_already_running(client):
    client.post("/start")

    response = client.post("/start")

    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "Bot is already running"}


def test_start_bot_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr("src.main.Config.CONTROL_TOKEN", "secret-token")

    response = client.post("/start")

    assert response.status_code == 401
    assert response.get_json() == {"status": "error", "message": "Unauthorized"}


def test_start_bot_accepts_bearer_token_when_configured(client, monkeypatch):
    monkeypatch.setattr("src.main.Config.CONTROL_TOKEN", "secret-token")

    response = client.post("/start", headers={"Authorization": "Bearer secret-token"})

    assert response.status_code == 200
    assert response.get_json() == {"status": "Bot started"}


def test_stop_bot(client):
    client.post("/start")
    response = client.post("/stop")
    assert response.status_code == 200
    data = response.get_json()
    assert data == {"status": "Bot stopped", "state": "stopped"}


def test_stop_bot_is_idempotent_when_already_stopped(client):
    response = client.post("/stop")

    assert response.status_code == 200
    assert response.get_json() == {"status": "Bot stopped", "state": "stopped"}


def test_stop_bot_reports_timeout_state(client):
    client.application.bot.stop = Mock(return_value=False)
    client.post("/start")

    response = client.post("/stop")

    assert response.status_code == 200
    assert response.get_json() == {"status": "Bot stop timed out", "state": "stopping"}


def test_start_bot_recovers_after_timed_out_stop(client):
    client.post("/start")
    client.application.bot.stop = Mock(return_value=False)

    stop_response = client.post("/stop")
    assert stop_response.get_json() == {"status": "Bot stop timed out", "state": "stopping"}

    start_response = client.post("/start")

    assert start_response.status_code == 400
    assert start_response.get_json() == {"status": "error", "message": "Bot is already running"}


def test_start_bot_recovers_once_old_worker_exits_after_timeout(client):
    client.post("/start")
    old_thread = client.application.bot.thread
    client.application.bot.stop = Mock(return_value=False)

    stop_response = client.post("/stop")
    assert stop_response.get_json() == {"status": "Bot stop timed out", "state": "stopping"}

    if old_thread is not None:
        client.application.bot.thread = None
        client.application.bot.is_running = False

    start_response = client.post("/start")

    assert start_response.status_code == 200
    assert start_response.get_json() == {"status": "Bot started"}
    assert client.application.bot.thread is not None
    assert client.application.bot.thread is not old_thread


def test_stop_bot_accepts_bearer_token_when_configured(client, monkeypatch):
    monkeypatch.setattr("src.main.Config.CONTROL_TOKEN", "secret-token")
    client.post("/start", headers={"Authorization": "Bearer secret-token"})

    response = client.post("/stop", headers={"Authorization": "Bearer secret-token"})

    assert response.status_code == 200
    assert response.get_json() == {"status": "Bot stopped", "state": "stopped"}


def test_stop_bot_rejects_wrong_token_when_configured(client, monkeypatch):
    monkeypatch.setattr("src.main.Config.CONTROL_TOKEN", "secret-token")

    response = client.post("/stop", headers={"Authorization": "Bearer wrong-token"})

    assert response.status_code == 401
    assert response.get_json() == {"status": "error", "message": "Unauthorized"}


def test_reset_bot_requires_token_when_configured(client, monkeypatch):
    monkeypatch.setattr("src.main.Config.CONTROL_TOKEN", "secret-token")

    response = client.post("/reset")

    assert response.status_code == 401
    assert response.get_json() == {"status": "error", "message": "Unauthorized"}


def test_reset_bot_accepts_bearer_token_when_configured(client, monkeypatch):
    monkeypatch.setattr("src.main.Config.CONTROL_TOKEN", "secret-token")
    client.post("/start", headers={"Authorization": "Bearer secret-token"})

    response = client.post("/reset", headers={"Authorization": "Bearer secret-token"})

    assert response.status_code == 200
    assert response.get_json() == {"status": "Trend reset completed"}


def test_health_remains_open_when_control_token_configured(client, monkeypatch):
    monkeypatch.setattr("src.main.Config.CONTROL_TOKEN", "secret-token")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.data == b"Healthy"


def test_trends_remains_open_when_control_token_configured(client, monkeypatch, test_scraper):
    monkeypatch.setattr("src.main.Config.CONTROL_TOKEN", "secret-token")

    response = client.get("/trends")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "data" in data


def test_get_trends(client, test_scraper):
    response = client.get("/trends")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "data" in data


def test_get_trends_returns_error_payload(client):
    client.application.scraper.scrape_trends = Mock(return_value={"status": "error", "message": "boom"})
    with patch.object(client.application.logger, "warning") as log_warning:
        response = client.get("/trends")

    assert response.status_code == 502
    assert response.get_json() == {"status": "error", "message": "boom"}
    log_warning.assert_called_once_with(
        "Trend scraper reported failure: %s", "boom"
    )


def test_get_trends_returns_json_on_exception(client):
    def boom():
        raise RuntimeError("boom")

    client.application.scraper.scrape_trends = boom
    with patch.object(client.application.logger, "exception") as log_exception:
        response = client.get("/trends")

    assert response.status_code == 502
    assert response.get_json() == {"status": "error", "message": "Failed to fetch trends"}
    log_exception.assert_called_once_with("Trend scraping failed")


@pytest.mark.parametrize("result", [None, [], "oops"])
def test_get_trends_returns_json_on_malformed_result(client, result):
    client.application.scraper.scrape_trends = Mock(return_value=result)
    with patch.object(client.application.logger, "error") as log_error:
        response = client.get("/trends")

    assert response.status_code == 502
    assert response.get_json() == {"status": "error", "message": "Failed to fetch trends"}
    log_error.assert_called_once_with(
        "Trend scraper returned invalid result type: %s",
        type(result).__name__,
    )


@pytest.mark.parametrize("result", [{"status": "error"}, {"status": "success"}])
def test_get_trends_rejects_incomplete_status_payloads(client, result):
    client.application.scraper.scrape_trends = Mock(return_value=result)

    with patch.object(client.application.logger, "error") as log_error:
        response = client.get("/trends")

    assert response.status_code == 502
    assert response.get_json() == {"status": "error", "message": "Failed to fetch trends"}
    log_error.assert_called_once_with(
        "Trend scraper returned malformed payload: status=%r keys=%s",
        result.get("status"),
        sorted(result),
    )


@pytest.mark.parametrize("path", ["/start", "/missing"])
def test_routing_errors_use_json_error_shape(client, path):
    response = client.get(path)

    assert response.status_code in {404, 405}
    assert response.mimetype == "application/json"
    assert response.get_json()["status"] == "error"
    assert isinstance(response.get_json()["message"], str)


@pytest.mark.parametrize("path", ["/start", "/stop", "/reset"])
def test_uninitialized_control_endpoints_use_json_error_shape(path):
    from src.main import create_app

    response = create_app().test_client().post(path)

    assert response.status_code == 400
    assert response.get_json() == {"status": "error", "message": "Bot not initialized"}


def test_unhandled_endpoint_exception_uses_json_error_shape():
    from src.main import create_app

    app = create_app()

    @app.route("/_test-boom")
    def boom():
        raise RuntimeError("boom")

    response = app.test_client().get("/_test-boom")

    assert response.status_code == 500
    assert response.mimetype == "application/json"
    assert response.get_json() == {"status": "error", "message": "Internal server error"}


def test_runtime_app_factory_starts_single_bot_and_monitor():
    from src.main import create_runtime_app

    bot = Mock()
    scraper = Mock()
    monitor = Mock()

    with (
        patch("src.main.init_webhook") as init_webhook,
        patch("src.main.setup_logging") as setup_logging,
        patch("src.main.RSSParser") as rss_parser,
        patch("src.main.RSSBot", return_value=bot) as rss_bot,
        patch("src.main.Scraper", return_value=scraper),
        patch("src.main.ResourceMonitor", return_value=monitor) as resource_monitor,
    ):
        app = create_runtime_app()

    init_webhook.assert_called_once()
    setup_logging.assert_called_once()
    rss_bot.assert_called_once_with(rss_parser.return_value, interval=10)
    resource_monitor.assert_called_once()
    monitor.start.assert_called_once_with()
    bot.start.assert_called_once_with()
    assert app.bot is bot
    assert app.scraper is scraper
    assert app.extensions["resource_monitor"] is monitor
