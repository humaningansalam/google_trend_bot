import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Generic, Mapping, TypeVar
from urllib.parse import urlsplit

import requests


T = TypeVar("T")


def _request_failure_message(
    operation: str, error: requests.RequestException
) -> str:
    if error.response is not None:
        return f"{operation} failed with HTTP {error.response.status_code}"
    return f"{operation} request failed"


class RemoteJobState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"

    @property
    def is_terminal(self) -> bool:
        return self not in {RemoteJobState.PENDING, RemoteJobState.RUNNING}


class RemoteJobErrorCode(str, Enum):
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
    DOWNLOAD_FAILED = "download_failed"


@dataclass(frozen=True)
class RemoteJobError:
    code: RemoteJobErrorCode
    message: str
    remote_code: str | None = None


@dataclass(frozen=True)
class RemoteJobResult(Generic[T]):
    value: T | None = None
    error: RemoteJobError | None = None

    def __post_init__(self):
        if (self.value is None) == (self.error is None):
            raise ValueError("RemoteJobResult requires exactly one of value or error")

    @property
    def is_success(self) -> bool:
        return self.error is None

    @classmethod
    def success(cls, value: T):
        return cls(value=value)

    @classmethod
    def failure(
        cls,
        code: RemoteJobErrorCode,
        message: str,
        remote_code: str | None = None,
    ):
        return cls(
            error=RemoteJobError(
                code=code,
                message=message,
                remote_code=remote_code,
            )
        )


@dataclass(frozen=True)
class JobResultEnvelope:
    payload: object
    files: dict[str, str]


class PlaywrightJobClient:
    def __init__(
        self,
        server_url: str | None = None,
        poll_interval: float = 10,
        max_poll_attempts: int = 60,
        sleep=time.sleep,
    ):
        self.server_url = (
            server_url or os.getenv("PLAYWRIGHT_URL", "http://localhost:3000")
        ).rstrip("/")
        self.poll_interval = poll_interval
        self.max_poll_attempts = max_poll_attempts
        self.sleep = sleep

    def execute(
        self, script_path: str, job_name: str
    ) -> RemoteJobResult[JobResultEnvelope]:
        submission = self._submit(script_path, job_name)
        if not submission.is_success:
            return RemoteJobResult(error=submission.error)

        job_id = submission.value
        poll_result = self._poll(job_id)
        if not poll_result.is_success:
            return RemoteJobResult(error=poll_result.error)

        result = self._get_results(job_id, poll_result.value)
        if not result.is_success:
            return RemoteJobResult(error=result.error)
        return result

    def _submit(self, script_path: str, job_name: str) -> RemoteJobResult[str]:
        if not os.path.isfile(script_path):
            return RemoteJobResult.failure(
                RemoteJobErrorCode.SCRIPT_NOT_FOUND,
                f"Crawl script does not exist: {script_path}",
            )

        try:
            with open(script_path, "rb") as script_file:
                response = requests.post(
                    f"{self.server_url}/api/jobs/submit",
                    files={
                        "script_file": (
                            os.path.basename(script_path),
                            script_file,
                            "text/x-python",
                        )
                    },
                    data={"jobname": job_name},
                    timeout=30,
                )
            response.raise_for_status()
        except requests.RequestException as exc:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.SUBMISSION_FAILED,
                _request_failure_message("Remote job submission", exc),
            )
        except OSError:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.SUBMISSION_FAILED,
                "Remote crawl script could not be read",
            )
        try:
            payload = response.json()
        except ValueError:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.INVALID_RESPONSE,
                "Remote submit response is not valid JSON",
            )

        job_id = payload.get("job_id") if isinstance(payload, Mapping) else None
        if response.status_code != 202 or not isinstance(job_id, str) or not job_id:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.INVALID_RESPONSE,
                "Remote submit response must be HTTP 202 with a job_id",
            )
        return RemoteJobResult.success(job_id)

    def _poll(self, job_id: str) -> RemoteJobResult[RemoteJobState]:
        status_url = f"{self.server_url}/api/jobs/status/{job_id}"
        for attempt in range(self.max_poll_attempts):
            try:
                response = requests.get(status_url, timeout=10)
                if response.status_code == 404:
                    return RemoteJobResult.failure(
                        RemoteJobErrorCode.JOB_NOT_FOUND,
                        f"Remote job was not found: {job_id}",
                    )
                response.raise_for_status()
            except requests.RequestException as exc:
                if attempt + 1 == self.max_poll_attempts:
                    return RemoteJobResult.failure(
                        RemoteJobErrorCode.REMOTE_UNAVAILABLE,
                        _request_failure_message("Remote job status", exc),
                    )
                self.sleep(self.poll_interval)
                continue
            try:
                payload = response.json()
            except ValueError:
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.INVALID_RESPONSE,
                    "Remote status response is not valid JSON",
                )

            raw_state = payload.get("status") if isinstance(payload, Mapping) else None
            try:
                state = RemoteJobState(raw_state)
            except (TypeError, ValueError):
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.INVALID_RESPONSE,
                    "Remote status response contains an unknown job state",
                )

            if state.is_terminal:
                return RemoteJobResult.success(state)
            self.sleep(self.poll_interval)

        return RemoteJobResult.failure(
            RemoteJobErrorCode.JOB_TIMEOUT,
            f"Remote job did not finish after {self.max_poll_attempts} polls",
        )

    def _get_results(
        self, job_id: str, expected_state: RemoteJobState
    ) -> RemoteJobResult[JobResultEnvelope]:
        try:
            response = requests.get(
                f"{self.server_url}/api/jobs/results/{job_id}", timeout=30
            )
            if response.status_code == 404:
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.JOB_NOT_FOUND,
                    f"Remote job result was not found: {job_id}",
                )
            if response.status_code == 202:
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.RESULT_NOT_READY,
                    f"Remote job result is not ready: {job_id}",
                )
            response.raise_for_status()
        except requests.RequestException as exc:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.REMOTE_UNAVAILABLE,
                _request_failure_message("Remote job result", exc),
            )
        try:
            payload = response.json()
        except ValueError:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.INVALID_RESPONSE,
                "Remote result response is not valid JSON",
            )

        raw_state = payload.get("status") if isinstance(payload, Mapping) else None
        try:
            state = RemoteJobState(raw_state)
        except (TypeError, ValueError):
            return RemoteJobResult.failure(
                RemoteJobErrorCode.INVALID_RESPONSE,
                "Remote result response contains an unknown job state",
            )
        if state is not expected_state:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.INVALID_RESPONSE,
                "Remote result response does not match the terminal job state",
            )
        if not state.is_terminal:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.RESULT_NOT_READY,
                f"Remote job result is not ready: {job_id}",
            )
        if "result" not in payload:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.INVALID_RESPONSE,
                "Remote result response must contain a result field",
            )
        if payload["result"] is None:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.INVALID_RESPONSE,
                "Remote result field must not be null",
            )

        if state is not RemoteJobState.COMPLETED:
            result = payload["result"]
            if not isinstance(result, Mapping):
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.INVALID_RESPONSE,
                    "Remote terminal result must contain an error object",
                )
            remote_code = result.get("code")
            message = result.get("message")
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
            return RemoteJobResult.failure(
                error_codes[state],
                message,
                remote_code=remote_code,
            )

        files = payload.get("files") or {}
        if not isinstance(files, Mapping) or not all(
            isinstance(name, str) and isinstance(url, str)
            for name, url in files.items()
        ):
            return RemoteJobResult.failure(
                RemoteJobErrorCode.INVALID_RESPONSE,
                "Remote result files must be a string map",
            )
        return RemoteJobResult.success(
            JobResultEnvelope(payload=payload["result"], files=dict(files))
        )

    def download_files(
        self, job_id: str, files: Mapping[str, str]
    ) -> RemoteJobResult[list[Path]]:
        download_root = Path("downloads").resolve()
        download_dir = _resolve_child_path(download_root, job_id)
        if download_dir is None:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.DOWNLOAD_FAILED,
                "Remote job ID resolves outside the download directory",
            )

        try:
            download_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return RemoteJobResult.failure(
                RemoteJobErrorCode.DOWNLOAD_FAILED,
                "Download directory could not be created",
            )

        saved_files = []
        for filename, file_url in files.items():
            file_path = _resolve_child_path(download_dir, filename)
            if file_path is None:
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.DOWNLOAD_FAILED,
                    "Remote filename resolves outside the job directory",
                )
            if not _is_download_path(file_url):
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.INVALID_RESPONSE,
                    "Remote file URL does not match the download endpoint schema",
                )

            try:
                response = requests.get(
                    f"{self.server_url}{file_url}", stream=True, timeout=60
                )
                response.raise_for_status()
                with open(file_path, "wb") as output:
                    for chunk in response.iter_content(chunk_size=8192):
                        output.write(chunk)
            except requests.RequestException as exc:
                message = _request_failure_message(
                    "Remote file download", exc
                )
                logging.error("%s", message)
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.DOWNLOAD_FAILED,
                    message,
                )
            except OSError:
                logging.error("Remote file could not be saved", exc_info=True)
                return RemoteJobResult.failure(
                    RemoteJobErrorCode.DOWNLOAD_FAILED,
                    "Remote file could not be saved",
                )
            saved_files.append(file_path)
        return RemoteJobResult.success(saved_files)


def _resolve_child_path(base_dir: Path, child: str) -> Path | None:
    try:
        resolved_path = (base_dir / child).resolve()
    except (OSError, RuntimeError, TypeError):
        return None
    if resolved_path == base_dir or not resolved_path.is_relative_to(base_dir):
        return None
    return resolved_path


def _is_download_path(value: str) -> bool:
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return False
    parts = PurePosixPath(parsed.path).parts
    return len(parts) == 6 and parts[:4] == ("/", "api", "jobs", "download")
