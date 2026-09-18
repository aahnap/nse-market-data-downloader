from datetime import date

import pytest

from nse_downloader.config_loader import CommonConfig, DatasetConfig, AppConfig
from nse_downloader.exceptions import HTTPStatusError
from nse_downloader import pipeline as pipeline_mod


def _make_config():
    common = CommonConfig(
        base_url="https://www.nseindia.com",
        user_agent="test",
        request_timeout_seconds=5,
        max_retries=1,
        backoff_base_seconds=0,
        warmup_pause_seconds=0,
    )
    datasets = {
        "good-one": DatasetConfig(
            key="good-one",
            display_name="Good One",
            page_url="https://www.nseindia.com/x",
            api_urls={"only": "https://www.nseindia.com/api/good"},
            file_prefix="good_one",
            required_columns=["symbol"],
        ),
        "bad-one": DatasetConfig(
            key="bad-one",
            display_name="Bad One",
            page_url="https://www.nseindia.com/y",
            api_urls={"only": "https://www.nseindia.com/api/bad"},
            file_prefix="bad_one",
            required_columns=["symbol"],
        ),
    }
    return AppConfig(common=common, datasets=datasets)


class FakeClient:
    """Stands in for NSEClient so tests don't touch the network at all."""

    def __init__(self, common):
        pass

    def fetch_json(self, api_url, referer_url):
        if "bad" in api_url:
            raise HTTPStatusError(500, "simulated failure")
        return {"data": [{"symbol": "TCS"}, {"symbol": "INFY"}]}


def test_one_dataset_failing_does_not_block_the_others(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_mod, "NSEClient", FakeClient)

    config = _make_config()
    results = pipeline_mod.run_all(
        config=config,
        output_dir=str(tmp_path),
        trading_date=date(2026, 9, 17),
    )

    by_key = {r.dataset_key: r for r in results}
    assert by_key["good-one"].success is True
    assert by_key["good-one"].row_count == 2
    assert by_key["bad-one"].success is False
    assert "simulated failure" in by_key["bad-one"].error

    # The good dataset's CSV should exist even though the bad one failed.
    files = list(tmp_path.glob("good_one_*.csv"))
    assert len(files) == 1
    bad_files = list(tmp_path.glob("bad_one_*.csv"))
    assert len(bad_files) == 0


def test_run_dataset_single_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_mod, "NSEClient", FakeClient)
    config = _make_config()

    results = pipeline_mod.run_all(
        config=config,
        output_dir=str(tmp_path),
        trading_date=date(2026, 9, 17),
        dataset_keys=["good-one"],
    )
    assert len(results) == 1
    assert results[0].dataset_key == "good-one"
