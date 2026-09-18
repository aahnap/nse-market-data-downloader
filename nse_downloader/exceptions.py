"""Custom exceptions used across the pipeline.

Having named exceptions (instead of just letting raw requests/JSON errors
bubble up) makes it possible to log *why* a dataset failed, and lets the
runner decide what's recoverable vs not.
"""


class NSEDownloaderError(Exception):
    """Base class for all errors raised by this application."""


class NetworkError(NSEDownloaderError):
    """Raised for connection errors, timeouts, and DNS failures."""


class HTTPStatusError(NSEDownloaderError):
    """Raised when the server responds with a non-2xx status code."""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(message or f"HTTP {status_code}")


class EmptyResponseError(NSEDownloaderError):
    """Raised when the server responds but the body is empty."""


class InvalidResponseError(NSEDownloaderError):
    """Raised when the response body isn't valid/parseable JSON."""


class UnexpectedFormatError(NSEDownloaderError):
    """Raised when JSON is valid but doesn't contain the data we expect."""


class ValidationError(NSEDownloaderError):
    """Raised when the parsed dataset fails validation checks."""
