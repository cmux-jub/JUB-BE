from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    BANK_LINK_REQUIRED = "BANK_LINK_REQUIRED"
    LABELING_REQUIRED = "LABELING_REQUIRED"
    CHATBOT_QUOTA_EXCEEDED = "CHATBOT_QUOTA_EXCEEDED"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppException(Exception):  # noqa: N818
    def __init__(self, code: ErrorCode | str, status_code: int, message: str) -> None:
        self.code = str(code)
        self.status_code = status_code
        self.message = message
        super().__init__(message)
