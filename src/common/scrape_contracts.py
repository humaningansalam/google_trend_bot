from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class ScrapeErrorCode(str, Enum):
    CRAWL_FAILED = "crawl_failed"
    INVALID_RESPONSE = "invalid_response"
    REMOTE_SCRIPT_NOT_FOUND = "remote_script_not_found"
    REMOTE_SUBMISSION_FAILED = "remote_submission_failed"
    REMOTE_JOB_NOT_FOUND = "remote_job_not_found"
    REMOTE_JOB_FAILED = "remote_job_failed"
    REMOTE_JOB_TIMEOUT = "remote_job_timeout"
    REMOTE_RESULT_NOT_READY = "remote_result_not_ready"
    REMOTE_DOWNLOAD_FAILED = "remote_download_failed"
    REMOTE_UNAVAILABLE = "remote_unavailable"


class ScrapeWireStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True)
class ScrapeError:
    code: ScrapeErrorCode
    message: str


@dataclass(frozen=True)
class ScrapeResult:
    data: list[dict[str, Any]] | None = None
    error: ScrapeError | None = None

    def __post_init__(self):
        if (self.data is None) == (self.error is None):
            raise ValueError("ScrapeResult requires exactly one of data or error")

    @property
    def is_success(self) -> bool:
        return self.error is None

    def to_wire(self) -> dict[str, object]:
        if self.is_success:
            return {"status": "success", "data": self.data}
        return {
            "status": "error",
            "error": {
                "code": self.error.code.value,
                "message": self.error.message,
            },
        }

    @classmethod
    def success(cls, data: list[dict[str, Any]]):
        return cls(data=data)

    @classmethod
    def failure(cls, code: ScrapeErrorCode, message: str):
        return cls(error=ScrapeError(code=code, message=message))

    @classmethod
    def from_wire(cls, payload: object):
        if not isinstance(payload, Mapping):
            return cls.failure(
                ScrapeErrorCode.INVALID_RESPONSE,
                "Scraper returned a non-object response",
            )

        try:
            status = ScrapeWireStatus(payload.get("status"))
        except (TypeError, ValueError):
            return cls.failure(
                ScrapeErrorCode.INVALID_RESPONSE,
                "Scraper response contains an unknown status",
            )

        if status is ScrapeWireStatus.SUCCESS:
            if set(payload) != {"status", "data"}:
                return cls.failure(
                    ScrapeErrorCode.INVALID_RESPONSE,
                    "Scraper success response contains unexpected fields",
                )
            data = payload.get("data")
            if not isinstance(data, list) or not all(
                isinstance(item, dict) for item in data
            ):
                return cls.failure(
                    ScrapeErrorCode.INVALID_RESPONSE,
                    "Scraper success response must contain a list of objects",
                )
            return cls.success(data)

        if status is ScrapeWireStatus.ERROR:
            if set(payload) != {"status", "error"}:
                return cls.failure(
                    ScrapeErrorCode.INVALID_RESPONSE,
                    "Scraper error response contains unexpected fields",
                )
            error = payload.get("error")
            if not isinstance(error, Mapping):
                return cls.failure(
                    ScrapeErrorCode.INVALID_RESPONSE,
                    "Scraper error response must contain an error object",
                )
            if set(error) != {"code", "message"}:
                return cls.failure(
                    ScrapeErrorCode.INVALID_RESPONSE,
                    "Scraper error object contains unexpected fields",
                )
            code = error.get("code")
            message = error.get("message")
            try:
                error_code = ScrapeErrorCode(code)
            except (TypeError, ValueError):
                return cls.failure(
                    ScrapeErrorCode.INVALID_RESPONSE,
                    "Scraper error response contains an unknown error code",
                )
            if not isinstance(message, str) or not message:
                return cls.failure(
                    ScrapeErrorCode.INVALID_RESPONSE,
                    "Scraper error response must contain a message",
                )
            return cls.failure(error_code, message)

        raise AssertionError("Unhandled scrape wire status")
