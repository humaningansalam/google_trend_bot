import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Generic, TypeVar
from urllib.parse import urlsplit

import requests

T = TypeVar("T")
DEFAULT_SERVER_URL = "http://localhost:3000"
SUBMISSION_TIMEOUT_SECONDS = 30
STATUS_TIMEOUT_SECONDS = 10
RESULT_TIMEOUT_SECONDS = 30
HTTP_ACCEPTED = 202
HTTP_NOT_FOUND = 404


class RemoteJobState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"

    @property
    def is_terminal(self) -> bool:
        return self not in {RemoteJobState.PENDING, RemoteJobState.RUNNING}


class RemoteJobErrorCode(StrEnum):
    SCRIPT_NOT_FOUND = "script_not_found"
    SUBMISSION_FAILED = "submission_failed"
    INVALID_RESPONSE = "invalid_response"
    JOB_NOT_FOUND = "job_not_found"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"
    JOB_INTERRUPTED = "job_interrupted"
    JOB_TIMEOUT = "job_timeout"
    RESULT_NOT_READY = "result_not_ready"
    REMOTE_UNAVAILABLE = "remote_unavailable"


@dataclass(frozen=True, slots=True)
class RemoteJobError:
    code: RemoteJobErrorCode
    message: str
    remote_code: str | None = None


@dataclass(frozen=True, slots=True)
class RemoteJobResult(Generic[T]):
    value: T | None = None
    error: RemoteJobError | None = None

    def __post_init__(self) -> None:
        if (self.value is None) == (self.error is None):
            raise ValueError("RemoteJobResult requires exactly one value or error")

    @property
    def is_success(self) -> bool:
        return self.error is None

    @classmethod
    def success(cls, value: T) -> "RemoteJobResult[T]":
        return cls(value=value)

    @classmethod
    def failure(
        cls,
        code: RemoteJobErrorCode,
        message: str,
        remote_code: str | None = None,
    ) -> "RemoteJobResult[T]":
        return cls(
            error=RemoteJobError(
                code=code,
                message=message,
                remote_code=remote_code,
            )
        )


class PlaywrightJobClient:
    def __init__(
        self,
        server_url: str | None = None,
        *,
        poll_interval_seconds: float = 10,
        max_poll_attempts: int = 60,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if poll_interval_seconds < 0:
            raise ValueError("poll_interval_seconds must not be negative")
        if max_poll_attempts <= 0:
            raise ValueError("max_poll_attempts must be positive")

        configured_url = server_url or os.getenv(
            "PLAYWRIGHT_URL",
            DEFAULT_SERVER_URL,
        )
        self.server_url = _validated_server_url(configured_url)
        self.poll_interval_seconds = poll_interval_seconds
        self.max_poll_attempts = max_poll_attempts
        self._sleep = sleep

    def execute(
        self,
        script_path: str | Path,
        job_name: str,
    ) -> RemoteJobResult[object]:
        submission = self._submit_job(Path(script_path), job_name)
        if not submission.is_success:
            return RemoteJobResult(error=submission.error)

        job_id = submission.value
        if job_id is None:
            raise AssertionError("Successful submission is missing its job ID")

        terminal_state = self._wait_for_terminal_state(job_id)
        if not terminal_state.is_success:
            return RemoteJobResult(error=terminal_state.error)

        expected_state = terminal_state.value
        if expected_state is None:
            raise AssertionError("Successful polling is missing its job state")
        return self._fetch_result_payload(job_id, expected_state)

    def _submit_job(
        self,
        script_path: Path,
        job_name: str,
    ) -> RemoteJobResult[str]:
        if not script_path.is_file():
            return RemoteJobResult.failure(
                RemoteJobErrorCode.SCRIPT_NOT_FOUND,
                "Remote crawl script is not available",
            )

        try:
            with script_path.open("rb") as script_file:
                response = requests.post(
                    f"{self.server_url}/api/jobs/submit",
                    files={
                        "script_file": (
                            script_path.name,
                            script_file,
                            "text/x-python",
                        )
                    },
                    data={"jobname": job_name},
                    timeout=SUBMISSION_TIMEOUT_SECONDS,
                )
            response.raise_for_status()
        except requests.RequestException as error:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.SUBMISSION_FAILED,
                _request_failure_message("Remote job submission", error),
            )
        except OSError:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.SUBMISSION_FAILED,
                "Remote crawl script could not be read",
            )

        payload = _decode_json_object(
            response,
            "Remote submit response is not valid JSON",
        )
        if isinstance(payload, RemoteJobResult):
            return payload

        job_id = payload.get("job_id")
        if (
            response.status_code != HTTP_ACCEPTED
            or not isinstance(job_id, str)
            or not job_id
        ):
            return RemoteJobResult.failure(
                RemoteJobErrorCode.INVALID_RESPONSE,
                "Remote submit response must be HTTP 202 with a job_id",
            )
        return RemoteJobResult.success(job_id)

    def _wait_for_terminal_state(
        self,
        job_id: str,
    ) -> RemoteJobResult[RemoteJobState]:
        status_url = f"{self.server_url}/api/jobs/status/{job_id}"
        for attempt_number in range(1, self.max_poll_attempts + 1):
            try:
                response = requests.get(
                    status_url,
                    timeout=STATUS_TIMEOUT_SECONDS,
                )
                if response.status_code == HTTP_NOT_FOUND:
                    return RemoteJobResult.failure(
                        RemoteJobErrorCode.JOB_NOT_FOUND,
                        f"Remote job was not found: {job_id}",
                    )
                response.raise_for_status()
            except requests.RequestException as error:
                if attempt_number == self.max_poll_attempts:
                    return RemoteJobResult.failure(
                        RemoteJobErrorCode.REMOTE_UNAVAILABLE,
                        _request_failure_message("Remote job status", error),
                    )
                self._sleep(self.poll_interval_seconds)
                continue

            payload = _decode_json_object(
                response,
                "Remote status response is not valid JSON",
            )
            if isinstance(payload, RemoteJobResult):
                return payload

            raw_state = payload.get("status")
            try:
                state = RemoteJobState(raw_state)
            except (TypeError, ValueError):
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.INVALID_RESPONSE,
                    "Remote status response contains an unknown job state",
                )

            if state.is_terminal:
                return RemoteJobResult.success(state)
            if attempt_number < self.max_poll_attempts:
                self._sleep(self.poll_interval_seconds)

        return RemoteJobResult.failure(
            RemoteJobErrorCode.JOB_TIMEOUT,
            f"Remote job did not finish after {self.max_poll_attempts} polls",
        )

    def _fetch_result_payload(
        self,
        job_id: str,
        expected_state: RemoteJobState,
    ) -> RemoteJobResult[object]:
        try:
            response = requests.get(
                f"{self.server_url}/api/jobs/results/{job_id}",
                timeout=RESULT_TIMEOUT_SECONDS,
            )
            if response.status_code == HTTP_NOT_FOUND:
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.JOB_NOT_FOUND,
                    f"Remote job result was not found: {job_id}",
                )
            if response.status_code == HTTP_ACCEPTED:
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.RESULT_NOT_READY,
                    f"Remote job result is not ready: {job_id}",
                )
            response.raise_for_status()
        except requests.RequestException as error:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.REMOTE_UNAVAILABLE,
                _request_failure_message("Remote job result", error),
            )

        payload = _decode_json_object(
            response,
            "Remote result response is not valid JSON",
        )
        if isinstance(payload, RemoteJobResult):
            return payload

        state_result = _parse_result_state(payload, expected_state)
        if not state_result.is_success:
            return RemoteJobResult(error=state_result.error)

        if "result" not in payload or payload["result"] is None:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.INVALID_RESPONSE,
                "Remote result response must contain a non-null result field",
            )

        if expected_state is RemoteJobState.COMPLETED:
            return RemoteJobResult.success(payload["result"])
        return _terminal_failure(payload["result"], expected_state)


def _validated_server_url(value: str) -> str:
    normalized_url = value.strip().rstrip("/")
    parsed_url = urlsplit(normalized_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("PLAYWRIGHT_URL must be an absolute HTTP(S) URL")
    if parsed_url.query or parsed_url.fragment:
        raise ValueError("PLAYWRIGHT_URL must not contain a query or fragment")
    return normalized_url


def _request_failure_message(
    operation: str,
    error: requests.RequestException,
) -> str:
    if error.response is not None:
        return f"{operation} failed with HTTP {error.response.status_code}"
    return f"{operation} request failed"


def _decode_json_object(
    response: requests.Response,
    invalid_json_message: str,
) -> Mapping[str, object] | RemoteJobResult[object]:
    try:
        payload = response.json()
    except ValueError:
        return RemoteJobResult.failure(
            RemoteJobErrorCode.INVALID_RESPONSE,
            invalid_json_message,
        )
    if not isinstance(payload, Mapping):
        return RemoteJobResult.failure(
            RemoteJobErrorCode.INVALID_RESPONSE,
            "Remote response must be a JSON object",
        )
    return payload


def _parse_result_state(
    payload: Mapping[str, object],
    expected_state: RemoteJobState,
) -> RemoteJobResult[RemoteJobState]:
    try:
        actual_state = RemoteJobState(payload.get("status"))
    except (TypeError, ValueError):
        return RemoteJobResult.failure(
            RemoteJobErrorCode.INVALID_RESPONSE,
            "Remote result response contains an unknown job state",
        )
    if actual_state is not expected_state:
        return RemoteJobResult.failure(
            RemoteJobErrorCode.INVALID_RESPONSE,
            "Remote result response does not match the terminal job state",
        )
    if not actual_state.is_terminal:
        return RemoteJobResult.failure(
            RemoteJobErrorCode.RESULT_NOT_READY,
            "Remote job result is not ready",
        )
    return RemoteJobResult.success(actual_state)


def _terminal_failure(
    raw_result: object,
    state: RemoteJobState,
) -> RemoteJobResult[object]:
    if not isinstance(raw_result, Mapping):
        return RemoteJobResult.failure(
            RemoteJobErrorCode.INVALID_RESPONSE,
            "Remote terminal result must contain an error object",
        )

    remote_code = raw_result.get("code")
    message = raw_result.get("message")
    if not isinstance(remote_code, str) or not remote_code:
        return RemoteJobResult.failure(
            RemoteJobErrorCode.INVALID_RESPONSE,
            "Remote terminal error must contain a code",
        )
    if not isinstance(message, str) or not message:
        return RemoteJobResult.failure(
            RemoteJobErrorCode.INVALID_RESPONSE,
            "Remote terminal error must contain a message",
        )

    error_codes = {
        RemoteJobState.FAILED: RemoteJobErrorCode.JOB_FAILED,
        RemoteJobState.CANCELLED: RemoteJobErrorCode.JOB_CANCELLED,
        RemoteJobState.INTERRUPTED: RemoteJobErrorCode.JOB_INTERRUPTED,
    }
    error_code = error_codes.get(state)
    if error_code is None:
        return RemoteJobResult.failure(
            RemoteJobErrorCode.INVALID_RESPONSE,
            "Remote terminal state does not describe a failure",
        )
    return RemoteJobResult.failure(
        error_code,
        message,
        remote_code=remote_code,
    )
