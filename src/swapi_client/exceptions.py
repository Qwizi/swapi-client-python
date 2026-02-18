from __future__ import annotations

from typing import Any


class SWException(Exception):
    """Base exception for all SW API client errors."""


class SWHTTPError(SWException):
    """Raised when the API returns an HTTP error response.

    Attributes:
        status_code:   HTTP status code (e.g. 404).
        response_data: Parsed JSON body (dict/list) or raw text string.
        message:       Human-readable error message.
    """

    def __init__(self, message: str, *, status_code: int, response_data: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

    def __repr__(self) -> str:
        return f"{type(self).__name__}(status_code={self.status_code}, message={str(self)!r})"


class SWAuthenticationError(SWHTTPError):
    """401 — Missing or invalid authentication token."""


class SWForbiddenError(SWHTTPError):
    """403 — Authenticated but not authorised to access this resource."""


class SWNotFoundError(SWHTTPError):
    """404 — Requested resource does not exist."""


class SWValidationError(SWHTTPError):
    """422 — Request payload failed server-side validation.

    Attributes:
        errors: Validation error details returned by the API (dict or list).
    """

    def __init__(self, message: str, *, status_code: int, response_data: Any = None) -> None:
        super().__init__(message, status_code=status_code, response_data=response_data)
        if isinstance(response_data, dict):
            self.errors: Any = response_data.get("errors") or response_data
        else:
            self.errors = response_data


class SWRateLimitError(SWHTTPError):
    """429 — Too many requests."""


class SWServerError(SWHTTPError):
    """5xx — Unexpected server-side error."""


class SWConnectionError(SWException):
    """Raised on network connectivity problems (DNS failure, timeout, etc.)."""


# ── Mapping: HTTP status code → exception class ───────────────────────────────

_STATUS_MAP: dict[int, type[SWHTTPError]] = {
    401: SWAuthenticationError,
    403: SWForbiddenError,
    404: SWNotFoundError,
    422: SWValidationError,
    429: SWRateLimitError,
}


def _http_error_for_status(
    status_code: int,
    message: str,
    response_data: Any,
) -> SWHTTPError:
    """Return the most specific SWHTTPError subclass for *status_code*."""
    if status_code in _STATUS_MAP:
        cls = _STATUS_MAP[status_code]
    elif status_code >= 500:
        cls = SWServerError
    else:
        cls = SWHTTPError
    return cls(message, status_code=status_code, response_data=response_data)
