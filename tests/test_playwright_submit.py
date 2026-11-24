from unittest.mock import Mock

import pytest
import requests

from src.clients.playwright_submit import (
    PlaywrightJobClient,
    RemoteJobErrorCode,
    RemoteJobResult,
)


def response(status_code: int = 200, payload: object = None) -> Mock:
    http_response = Mock(status_code=status_code)
    http_response.json.return_value = payload
    http_response.raise_for_status.return_value = None
    return http_response


def test_execute_returns_the_completed_result_payload(monkeypatch, tmp_path):
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
                    "status": "COMPLETED",
                    "result": {"status": "success", "data": []},
                    "files": {"unused.txt": "/api/jobs/download/job-1/unused.txt"},
                },
            ),
        ]
    )
    monkeypatch.setattr("src.clients.playwright_submit.requests.get", get)
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.execute(script, "google_trends_crawl")

    assert result == RemoteJobResult.success({"status": "success", "data": []})
    assert get.call_count == 2


def test_execute_reports_a_missing_script_without_network_calls(
    monkeypatch,
    tmp_path,
):
    post = Mock()
    monkeypatch.setattr("src.clients.playwright_submit.requests.post", post)
    client = PlaywrightJobClient(server_url="http://playwright-server")

    result = client.execute(tmp_path / "missing.py", "missing")

    assert result.error is not None
    assert result.error.code is RemoteJobErrorCode.SCRIPT_NOT_FOUND
    assert result.error.message == "Remote crawl script is not available"
    assert str(tmp_path) not in result.error.message
    post.assert_not_called()


def test_execute_rejects_an_unknown_job_state(monkeypatch, tmp_path):
    script = tmp_path / "crawl.py"
    script.write_text("pass", encoding="utf-8")
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=response(202, {"job_id": "job-1"})),
    )
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.get",
        Mock(return_value=response(200, {"status": "ALMOST_DONE"})),
    )

    result = PlaywrightJobClient(server_url="http://playwright-server").execute(
        script, "crawl"
    )

    assert result.error is not None
    assert result.error.code is RemoteJobErrorCode.INVALID_RESPONSE


def test_execute_distinguishes_invalid_json_from_transport_failure(
    monkeypatch,
    tmp_path,
):
    script = tmp_path / "crawl.py"
    script.write_text("pass", encoding="utf-8")
    invalid_response = response(202)
    invalid_response.json.side_effect = ValueError("invalid json")
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=invalid_response),
    )

    result = PlaywrightJobClient(server_url="http://playwright-server").execute(
        script, "crawl"
    )

    assert result.error is not None
    assert result.error.code is RemoteJobErrorCode.INVALID_RESPONSE


def test_poll_timeout_does_not_sleep_after_the_final_attempt(
    monkeypatch,
    tmp_path,
):
    script = tmp_path / "crawl.py"
    script.write_text("pass", encoding="utf-8")
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=response(202, {"job_id": "job-1"})),
    )
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.get",
        Mock(return_value=response(200, {"status": "RUNNING"})),
    )
    sleep = Mock()
    client = PlaywrightJobClient(
        server_url="http://playwright-server",
        poll_interval_seconds=1,
        max_poll_attempts=2,
        sleep=sleep,
    )

    result = client.execute(script, "crawl")

    assert result.error is not None
    assert result.error.code is RemoteJobErrorCode.JOB_TIMEOUT
    sleep.assert_called_once_with(1)


def test_failed_job_preserves_the_remote_error_code(monkeypatch, tmp_path):
    script = tmp_path / "crawl.py"
    script.write_text("pass", encoding="utf-8")
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=response(202, {"job_id": "job-1"})),
    )
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.get",
        Mock(
            side_effect=[
                response(200, {"status": "FAILED"}),
                response(
                    200,
                    {
                        "status": "FAILED",
                        "result": {
                            "code": "USER_SCRIPT_FAILED",
                            "message": "crawl exploded",
                        },
                    },
                ),
            ]
        ),
    )

    result = PlaywrightJobClient(server_url="http://playwright-server").execute(
        script, "crawl"
    )

    assert result.error is not None
    assert result.error.code is RemoteJobErrorCode.JOB_FAILED
    assert result.error.message == "crawl exploded"
    assert result.error.remote_code == "USER_SCRIPT_FAILED"


@pytest.mark.parametrize(
    ("state", "remote_code", "expected_code"),
    [
        ("CANCELLED", "JOB_CANCELLED", RemoteJobErrorCode.JOB_CANCELLED),
        (
            "INTERRUPTED",
            "SERVICE_SHUTDOWN",
            RemoteJobErrorCode.JOB_INTERRUPTED,
        ),
    ],
)
def test_execute_handles_all_terminal_failure_states(
    monkeypatch,
    tmp_path,
    state: str,
    remote_code: str,
    expected_code: RemoteJobErrorCode,
):
    script = tmp_path / "crawl.py"
    script.write_text("pass", encoding="utf-8")
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=response(202, {"job_id": "job-1"})),
    )
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.get",
        Mock(
            side_effect=[
                response(200, {"status": state}),
                response(
                    200,
                    {
                        "status": state,
                        "result": {
                            "code": remote_code,
                            "message": f"job ended as {state.lower()}",
                        },
                    },
                ),
            ]
        ),
    )

    result = PlaywrightJobClient(server_url="http://playwright-server").execute(
        script, "crawl"
    )

    assert result.error is not None
    assert result.error.code is expected_code
    assert result.error.remote_code == remote_code


def test_submission_failure_does_not_expose_authenticated_server_url(
    monkeypatch,
    tmp_path,
):
    script = tmp_path / "crawl.py"
    script.write_text("pass", encoding="utf-8")
    secret = "REMOTE_SUPERSECRET"
    server_url = f"http://user:{secret}@playwright-server"
    failed_response = requests.Response()
    failed_response.status_code = 500
    failed_response.url = f"{server_url}/api/jobs/submit"
    monkeypatch.setattr(
        "src.clients.playwright_submit.requests.post",
        Mock(return_value=failed_response),
    )

    result = PlaywrightJobClient(server_url=server_url).execute(script, "crawl")

    assert result.error is not None
    assert result.error.message == "Remote job submission failed with HTTP 500"
    assert secret not in result.error.message


@pytest.mark.parametrize(
    ("keyword_arguments", "message"),
    [
        ({"server_url": "not-a-url"}, "absolute HTTP"),
        (
            {"server_url": "http://playwright-server?token=secret"},
            "query or fragment",
        ),
        (
            {
                "server_url": "http://playwright-server",
                "poll_interval_seconds": -1,
            },
            "poll_interval_seconds",
        ),
        (
            {
                "server_url": "http://playwright-server",
                "max_poll_attempts": 0,
            },
            "max_poll_attempts",
        ),
    ],
)
def test_constructor_rejects_invalid_configuration(
    keyword_arguments: dict[str, object],
    message: str,
):
    with pytest.raises(ValueError, match=message):
        PlaywrightJobClient(**keyword_arguments)
