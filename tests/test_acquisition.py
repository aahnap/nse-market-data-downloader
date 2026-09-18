from unittest.mock import patch

import pytest
import responses

from nse_downloader.acquisition import NSEClient
from nse_downloader.config_loader import CommonConfig
from nse_downloader.exceptions import (
    EmptyResponseError,
    HTTPStatusError,
    InvalidResponseError,
    NetworkError,
)

COMMON = CommonConfig(
    base_url="https://www.nseindia.com",
    user_agent="test-agent",
    request_timeout_seconds=5,
    max_retries=3,
    backoff_base_seconds=0,  # keep tests fast
    warmup_pause_seconds=0,
)

API_URL = "https://www.nseindia.com/api/some-endpoint"
PAGE_URL = "https://www.nseindia.com/market-data/some-page"


def _client():
    return NSEClient(COMMON)


@responses.activate
@patch("nse_downloader.acquisition.time.sleep", return_value=None)
def test_fetch_json_success(_sleep):
    responses.add(responses.GET, COMMON.base_url, body="<html></html>", status=200)
    responses.add(responses.GET, API_URL, json={"data": [{"symbol": "TCS"}]}, status=200)

    result = _client().fetch_json(API_URL, PAGE_URL)
    assert result == {"data": [{"symbol": "TCS"}]}


@responses.activate
@patch("nse_downloader.acquisition.time.sleep", return_value=None)
def test_fetch_json_retries_on_500_then_succeeds(_sleep):
    responses.add(responses.GET, COMMON.base_url, body="<html></html>", status=200)
    responses.add(responses.GET, API_URL, status=500)
    responses.add(responses.GET, API_URL, status=500)
    responses.add(responses.GET, API_URL, json={"data": [{"symbol": "OK"}]}, status=200)

    result = _client().fetch_json(API_URL, PAGE_URL)
    assert result["data"][0]["symbol"] == "OK"


@responses.activate
@patch("nse_downloader.acquisition.time.sleep", return_value=None)
def test_fetch_json_raises_http_error_after_exhausting_retries(_sleep):
    responses.add(responses.GET, COMMON.base_url, body="<html></html>", status=200)
    for _ in range(COMMON.max_retries):
        responses.add(responses.GET, API_URL, status=503)

    with pytest.raises(HTTPStatusError):
        _client().fetch_json(API_URL, PAGE_URL)


@responses.activate
@patch("nse_downloader.acquisition.time.sleep", return_value=None)
def test_fetch_json_client_error_does_not_retry(_sleep):
    responses.add(responses.GET, COMMON.base_url, body="<html></html>", status=200)
    responses.add(responses.GET, API_URL, status=404)

    with pytest.raises(HTTPStatusError) as exc_info:
        _client().fetch_json(API_URL, PAGE_URL)
    assert exc_info.value.status_code == 404
    # Only one call to the API endpoint -- 404s aren't retried.
    api_calls = [c for c in responses.calls if c.request.url == API_URL]
    assert len(api_calls) == 1


@responses.activate
@patch("nse_downloader.acquisition.time.sleep", return_value=None)
def test_fetch_json_empty_response_raises(_sleep):
    responses.add(responses.GET, COMMON.base_url, body="<html></html>", status=200)
    responses.add(responses.GET, API_URL, body="", status=200)

    with pytest.raises(EmptyResponseError):
        _client().fetch_json(API_URL, PAGE_URL)


@responses.activate
@patch("nse_downloader.acquisition.time.sleep", return_value=None)
def test_fetch_json_invalid_json_raises(_sleep):
    responses.add(responses.GET, COMMON.base_url, body="<html></html>", status=200)
    responses.add(responses.GET, API_URL, body="not json at all", status=200)

    with pytest.raises(InvalidResponseError):
        _client().fetch_json(API_URL, PAGE_URL)


@patch("nse_downloader.acquisition.time.sleep", return_value=None)
def test_fetch_json_network_error_raises(_sleep):
    # No `responses.activate` registrations at all -> requests will raise
    # a ConnectionError since nothing is mocked for this URL.
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, COMMON.base_url, body="<html></html>", status=200)
        # Deliberately leave API_URL unregistered so `responses` raises
        # ConnectionError, simulating a real network failure.
        with pytest.raises(NetworkError):
            _client().fetch_json(API_URL, PAGE_URL)
