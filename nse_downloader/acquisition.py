"""
Acquisition layer: everything related to talking to NSE over HTTP.

NSE's site rejects requests that don't look like a browser and don't carry
cookies from an initial page visit, so a plain `requests.get(api_url)` will
usually come back as 401/403. The fix used here (and commonly documented
for this API) is:

    1. GET the public homepage first, with browser-like headers, to receive
       session cookies.
    2. Reuse that same `requests.Session` (and cookies) to call the JSON
       API endpoint, with a `Referer` header pointing at the relevant page.

This module deliberately knows nothing about CSV files or which columns a
dataset "should" have -- that's the validation/storage layers' job. Its
only responsibility is: give me a URL, I'll give you parsed JSON or a
clear, specific exception explaining what went wrong.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict

import requests

from .config_loader import CommonConfig
from .exceptions import (
    EmptyResponseError,
    HTTPStatusError,
    InvalidResponseError,
    NetworkError,
)

logger = logging.getLogger(__name__)


class NSEClient:
    """A small wrapper around requests.Session with NSE's quirks baked in."""

    def __init__(self, common: CommonConfig):
        self.common = common
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": common.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        self._warmed_up = False

    def _warm_up(self) -> None:
        """Visit the homepage once to pick up session cookies."""
        if self._warmed_up:
            return
        try:
            self.session.get(
                self.common.base_url,
                timeout=self.common.request_timeout_seconds,
            )
        except requests.exceptions.RequestException as exc:
            # Not fatal by itself -- the real API call below will fail
            # clearly if cookies were actually required.
            logger.warning("Cookie warm-up request failed: %s", exc)
        else:
            self._warmed_up = True
            time.sleep(self.common.warmup_pause_seconds)

    def fetch_json(self, api_url: str, referer_url: str) -> Dict[str, Any]:
        """
        Fetch `api_url` and return parsed JSON.

        Retries on network errors and 5xx responses using exponential
        backoff. Raises a specific NSEDownloaderError subclass on failure
        so the caller can log/handle it precisely.
        """
        self._warm_up()

        last_exc: Exception | None = None
        for attempt in range(1, self.common.max_retries + 1):
            try:
                response = self.session.get(
                    api_url,
                    headers={"Referer": referer_url},
                    timeout=self.common.request_timeout_seconds,
                )
            except requests.exceptions.Timeout as exc:
                last_exc = NetworkError(f"Timed out calling {api_url}: {exc}")
            except requests.exceptions.RequestException as exc:
                last_exc = NetworkError(f"Network error calling {api_url}: {exc}")
            else:
                if 500 <= response.status_code < 600:
                    last_exc = HTTPStatusError(
                        response.status_code,
                        f"Server error {response.status_code} from {api_url}",
                    )
                elif response.status_code >= 400:
                    # Client errors (401/403/404/...) are not worth retrying.
                    raise HTTPStatusError(
                        response.status_code,
                        f"Client error {response.status_code} from {api_url}",
                    )
                else:
                    return self._parse_json(response, api_url)

            if attempt < self.common.max_retries:
                sleep_for = self.common.backoff_base_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Attempt %d/%d failed for %s (%s). Retrying in %ds...",
                    attempt,
                    self.common.max_retries,
                    api_url,
                    last_exc,
                    sleep_for,
                )
                time.sleep(sleep_for)

        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _parse_json(response: requests.Response, api_url: str) -> Dict[str, Any]:
        if not response.content or not response.content.strip():
            raise EmptyResponseError(f"Empty response body from {api_url}")
        try:
            return response.json()
        except ValueError as exc:
            raise InvalidResponseError(
                f"Response from {api_url} was not valid JSON: {exc}"
            ) from exc
