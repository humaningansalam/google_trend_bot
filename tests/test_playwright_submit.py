import logging
from unittest.mock import Mock

import requests

from src.clients.playwright_submit import (
    JobResultEnvelope,
    PlaywrightJobClient,
    RemoteJobErrorCode,
    RemoteJobResult,
)


def response(status_code=200, payload=None):
    result = Mock(status_code=status_code)
    result.json.return_value = payload
    return result


def test_execute_returns_the_remote_result_envelope(monkeypatch, tmp_path):
    script = tmp_path / "crawl.py"
    script.write_text("async def crawl(): pass", encoding="utf-8")
    post = Mock(return_value=response(202, {"job_id": "job-1"}))
    get = Mock(
        side_effect=[
            response(200, {"status": "COMPLETED"}),
            response(
                200,
                {
                    "result": {"status": "success", "data": []},
                    "files": {},
                },
            ),
        ]
    )
    monkeypatch.setattr("src.clients.playwright_submit.requests.post", post)
    monkeypatch.setattr("src.clients.playwright_submit.requests.get", get)
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.execute(str(script), "google_trends_crawl")

    assert result.is_success
    assert result.value == JobResultEnvelope(
        payload={"status": "success", "data": []},
        files={},
    )


def test_execute_does_not_download_result_artifacts(monkeypatch, tmp_path):
    script = tmp_path / "crawl.py"
    script.write_text("async def crawl(): pass", encoding="utf-8")
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=response(202, {"job_id": "job-1"})),
    )
    get = Mock(
        side_effect=[
            response(200, {"status": "COMPLETED"}),
            response(
                200,
                {
                    "result": {
                        "status": "success",
                        "data": [{"trend": "Remote Trend"}],
                    },
                    "files": {
                        "artifact.txt": "/api/jobs/download/1"
                    },
                },
            ),
        ]
    )
    monkeypatch.setattr("src.clients.playwright_submit.requests.get", get)
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.execute(str(script), "google_trends_crawl")

    assert result == RemoteJobResult.success(
        JobResultEnvelope(
            payload={
                "status": "success",
                "data": [{"trend": "Remote Trend"}],
            },
            files={"artifact.txt": "/api/jobs/download/1"},
        )
    )
    assert get.call_count == 2


def test_execute_returns_a_typed_unknown_state_error(monkeypatch, tmp_path):
    script = tmp_path / "crawl.py"
    script.write_text("async def crawl(): pass", encoding="utf-8")
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=response(202, {"job_id": "job-1"})),
    )
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.get",
        Mock(return_value=response(200, {"status": "ALMOST_DONE"})),
    )
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.execute(str(script), "google_trends_crawl")

    assert result.error.code is RemoteJobErrorCode.INVALID_RESPONSE


def test_execute_distinguishes_invalid_json_from_transport_failure(
    monkeypatch, tmp_path
):
    script = tmp_path / "crawl.py"
    script.write_text("async def crawl(): pass", encoding="utf-8")
    invalid_response = response(202)
    invalid_response.json.side_effect = ValueError("invalid json")
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=invalid_response),
    )
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.execute(str(script), "google_trends_crawl")

    assert result.error.code is RemoteJobErrorCode.INVALID_RESPONSE


def test_execute_returns_a_typed_timeout(monkeypatch, tmp_path):
    script = tmp_path / "crawl.py"
    script.write_text("async def crawl(): pass", encoding="utf-8")
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=response(202, {"job_id": "job-1"})),
    )
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.get",
        Mock(return_value=response(200, {"status": "RUNNING"})),
    )
    client = PlaywrightJobClient(
        server_url="http://playwright-server",
        poll_interval=0,
        max_poll_attempts=2,
        sleep=Mock(),
    )

    result = client.execute(str(script), "google_trends_crawl")

    assert result.error.code is RemoteJobErrorCode.JOB_TIMEOUT


def test_execute_preserves_failed_job_as_a_typed_failure(monkeypatch, tmp_path):
    script = tmp_path / "crawl.py"
    script.write_text("async def crawl(): pass", encoding="utf-8")
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=response(202, {"job_id": "job-1"})),
    )
    get = Mock(return_value=response(200, {"status": "FAILED"}))
    monkeypatch.setattr("src.clients.playwright_submit.requests.get", get)
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.execute(str(script), "google_trends_crawl")

    assert result.error.code is RemoteJobErrorCode.JOB_FAILED
    get.assert_called_once_with(
        "http://playwright-server/api/jobs/status/job-1",
        timeout=10,
    )


def test_download_files_rejects_job_id_outside_download_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    get = Mock()
    monkeypatch.setattr("src.clients.playwright_submit.requests.get", get)
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.download_files(
        "../outside-job",
        {"artifact.txt": "/api/jobs/download/1"},
    )

    assert result.error.code is RemoteJobErrorCode.DOWNLOAD_FAILED
    get.assert_not_called()


def test_download_files_rejects_filename_outside_job_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    get = Mock()
    monkeypatch.setattr("src.clients.playwright_submit.requests.get", get)
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.download_files(
        "safe-job",
        {"../../outside-file.txt": "/api/jobs/download/2"},
    )

    assert result.error.code is RemoteJobErrorCode.DOWNLOAD_FAILED
    get.assert_not_called()


def test_download_files_rejects_noncanonical_download_url(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    get = Mock()
    monkeypatch.setattr("src.clients.playwright_submit.requests.get", get)
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.download_files(
        "safe-job",
        {"artifact.txt": "/other/api/jobs/download/2"},
    )

    assert result.error.code is RemoteJobErrorCode.INVALID_RESPONSE
    get.assert_not_called()


def test_download_files_saves_safe_result(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    file_response = Mock()
    file_response.iter_content.return_value = [b"safe", b" result"]
    get = Mock(return_value=file_response)
    monkeypatch.setattr("src.clients.playwright_submit.requests.get", get)
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.download_files(
        "safe-job",
        {"artifact.txt": "/api/jobs/download/3"},
    )

    assert result.is_success
    assert (
        tmp_path / "downloads" / "safe-job" / "artifact.txt"
    ).read_bytes() == b"safe result"
    get.assert_called_once_with(
        "http://playwright-server/api/jobs/download/3",
        stream=True,
        timeout=60,
    )


def test_download_files_does_not_log_authenticated_server_url(
    monkeypatch, tmp_path, caplog
):
    monkeypatch.chdir(tmp_path)
    secret = "REMOTE_SUPERSECRET"
    server_url = f"http://user:{secret}@playwright-server"
    failed_response = requests.Response()
    failed_response.status_code = 500
    failed_response.url = f"{server_url}/api/jobs/download/4"
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.get",
        Mock(return_value=failed_response),
    )
    client = PlaywrightJobClient(server_url=server_url)

    with caplog.at_level(logging.ERROR):
        result = client.download_files(
            "safe-job",
            {"artifact.txt": "/api/jobs/download/4"},
        )

    assert result.error.code is RemoteJobErrorCode.DOWNLOAD_FAILED
    assert result.error.message == "Remote file download failed with HTTP 500"
    assert secret not in result.error.message
    assert secret not in caplog.text
