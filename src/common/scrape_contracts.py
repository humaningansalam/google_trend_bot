from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Self


class ScrapeErrorCode(StrEnum):
    CRAWL_FAILED = "crawl_failed"
    INVALID_RESPONSE = "invalid_response"
    REMOTE_SCRIPT_NOT_FOUND = "remote_script_not_found"
    REMOTE_SUBMISSION_FAILED = "remote_submission_failed"
    REMOTE_JOB_NOT_FOUND = "remote_job_not_found"
    REMOTE_JOB_FAILED = "remote_job_failed"
    REMOTE_JOB_CANCELLED = "remote_job_cancelled"
    REMOTE_JOB_INTERRUPTED = "remote_job_interrupted"
    REMOTE_JOB_TIMEOUT = "remote_job_timeout"
    REMOTE_RESULT_NOT_READY = "remote_result_not_ready"
    REMOTE_UNAVAILABLE = "remote_unavailable"


class ScrapeStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScrapeError:
    code: ScrapeErrorCode
    message: str


@dataclass(frozen=True, slots=True)
class ScrapeResult:
    data: list[dict[str, Any]] | None = None
    error: ScrapeError | None = None

    def __post_init__(self) -> None:
        if (self.data is None) == (self.error is None):
            raise ValueError("ScrapeResult requires exactly one of data or error")

    @property
    def is_success(self) -> bool:
        return self.error is None

    def to_payload(self) -> dict[str, object]:
        if self.is_success:
            return {"status": ScrapeStatus.SUCCESS.value, "data": self.data}

        error = self.error
        if error is None:
            raise AssertionError("Failed scrape result is missing its error")
        return {
            "status": ScrapeStatus.ERROR.value,
            "error": {
                "code": error.code.value,
                "message": error.message,
            },
        }

    @classmethod
    def success(cls, data: list[dict[str, Any]]) -> Self:
        return cls(data=data)

    @classmethod
    def failure(cls, code: ScrapeErrorCode, message: str) -> Self:
        return cls(error=ScrapeError(code=code, message=message))

    @classmethod
    def invalid_response(cls, message: str) -> Self:
        return cls.failure(ScrapeErrorCode.INVALID_RESPONSE, message)

    @classmethod
    def from_payload(cls, payload: object) -> Self:
        if not isinstance(payload, Mapping):
            return cls.invalid_response("Scraper returned a non-object response")

        try:
            status = ScrapeStatus(payload.get("status"))
        except (TypeError, ValueError):
            return cls.invalid_response("Scraper response contains an unknown status")

        if status is ScrapeStatus.SUCCESS:
            return cls._parse_success_payload(payload)
        return cls._parse_error_payload(payload)

    @classmethod
    def _parse_success_payload(cls, payload: Mapping[object, object]) -> Self:
        if set(payload) != {"status", "data"}:
            return cls.invalid_response(
                "Scraper success response contains unexpected fields"
            )

        data = payload.get("data")
        if not isinstance(data, list) or not all(
            isinstance(item, dict) for item in data
        ):
            return cls.invalid_response(
                "Scraper success response must contain a list of objects"
            )
        return cls.success(data)

    @classmethod
    def _parse_error_payload(cls, payload: Mapping[object, object]) -> Self:
        if set(payload) != {"status", "error"}:
            return cls.invalid_response(
                "Scraper error response contains unexpected fields"
            )

        error_payload = payload.get("error")
        if not isinstance(error_payload, Mapping):
            return cls.invalid_response(
                "Scraper error response must contain an error object"
            )
        if set(error_payload) != {"code", "message"}:
            return cls.invalid_response(
                "Scraper error object contains unexpected fields"
            )

        raw_code = error_payload.get("code")
        message = error_payload.get("message")
        try:
            error_code = ScrapeErrorCode(raw_code)
        except (TypeError, ValueError):
            return cls.invalid_response(
                "Scraper error response contains an unknown error code"
            )
        if not isinstance(message, str) or not message:
            return cls.invalid_response("Scraper error response must contain a message")
        return cls.failure(error_code, message)
