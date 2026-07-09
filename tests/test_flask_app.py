from unittest.mock import Mock

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
    assert start_response.get_json() == {"status": "Bot is already running"}


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
    response = client.get("/trends")
    assert response.status_code == 502
    assert response.get_json() == {"status": "error", "message": "boom"}


def test_get_trends_returns_json_on_exception(client):
    def boom():
        raise RuntimeError("boom")

    client.application.scraper.scrape_trends = boom
    response = client.get("/trends")
    assert response.status_code == 502
    assert response.get_json() == {"status": "error", "message": "Failed to fetch trends"}


@pytest.mark.parametrize("result", [None, [], "oops"])
def test_get_trends_returns_json_on_malformed_result(client, result):
    client.application.scraper.scrape_trends = Mock(return_value=result)
    response = client.get("/trends")
    assert response.status_code == 502
    assert response.get_json() == {"status": "error", "message": "Failed to fetch trends"}
