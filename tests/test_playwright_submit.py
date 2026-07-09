import importlib

import src.clients.playwright_submit as playwright_submit


def test_playwright_submit_default_server_url_matches_example_env(monkeypatch):
    monkeypatch.delenv("PLAYWRIGHT_URL", raising=False)

    module = importlib.reload(playwright_submit)

    assert module.SERVER_URL == "http://localhost:3000"


def test_playwright_submit_server_url_uses_environment(monkeypatch):
    monkeypatch.setenv("PLAYWRIGHT_URL", "http://playwright-job-server:8080")

    module = importlib.reload(playwright_submit)

    assert module.SERVER_URL == "http://playwright-job-server:8080"
