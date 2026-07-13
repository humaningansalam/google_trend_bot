import importlib
from unittest.mock import Mock

import src.clients.playwright_submit as playwright_submit


def test_playwright_submit_default_server_url_matches_example_env(monkeypatch):
    monkeypatch.delenv("PLAYWRIGHT_URL", raising=False)

    module = importlib.reload(playwright_submit)

    assert module.SERVER_URL == "http://localhost:3000"


def test_playwright_submit_server_url_uses_environment(monkeypatch):
    monkeypatch.setenv("PLAYWRIGHT_URL", "http://playwright-job-server:8080")

    module = importlib.reload(playwright_submit)

    assert module.SERVER_URL == "http://playwright-job-server:8080"


def test_download_files_rejects_job_id_outside_download_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    get = Mock()
    monkeypatch.setattr(playwright_submit.requests, "get", get)

    playwright_submit.download_files(
        "../outside-job",
        {"artifact.txt": "/api/jobs/download/1"},
    )

    assert not (tmp_path / "outside-job" / "artifact.txt").exists()
    get.assert_not_called()


def test_download_files_rejects_filename_outside_job_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    get = Mock()
    monkeypatch.setattr(playwright_submit.requests, "get", get)

    playwright_submit.download_files(
        "safe-job",
        {"../../outside-file.txt": "/api/jobs/download/2"},
    )

    assert not (tmp_path / "outside-file.txt").exists()
    get.assert_not_called()


def test_download_files_saves_safe_result(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    response = Mock()
    response.iter_content.return_value = [b"safe", b" result"]
    get = Mock(return_value=response)
    monkeypatch.setattr(playwright_submit.requests, "get", get)
    monkeypatch.setattr(playwright_submit, "SERVER_URL", "http://playwright-server")

    playwright_submit.download_files(
        "safe-job",
        {"artifact.txt": "/api/jobs/download/3"},
    )

    assert (tmp_path / "downloads" / "safe-job" / "artifact.txt").read_bytes() == b"safe result"
    get.assert_called_once_with(
        "http://playwright-server/api/jobs/download/3",
        stream=True,
        timeout=60,
    )
