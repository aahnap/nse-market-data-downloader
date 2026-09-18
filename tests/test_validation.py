import pytest

from nse_downloader.exceptions import UnexpectedFormatError, ValidationError
from nse_downloader.validation import validate_records


def test_validate_records_happy_path():
    records = [
        {"symbol": "TCS", "series": "EQ", "ltp": "3950.5"},
        {"symbol": "INFY", "series": "EQ", "ltp": "1820.1"},
    ]
    df = validate_records(records, required_columns=["symbol", "ltp"], dataset_key="ds")
    assert len(df) == 2
    assert list(df["symbol"]) == ["TCS", "INFY"]


def test_validate_records_rejects_empty_list():
    with pytest.raises(ValidationError):
        validate_records([], required_columns=["symbol"], dataset_key="ds")


def test_validate_records_rejects_none():
    with pytest.raises(UnexpectedFormatError):
        validate_records(None, required_columns=["symbol"], dataset_key="ds")


def test_validate_records_rejects_non_list():
    with pytest.raises(UnexpectedFormatError):
        validate_records({"not": "a list"}, required_columns=["symbol"], dataset_key="ds")


def test_validate_records_rejects_missing_required_columns():
    records = [{"symbol": "TCS"}]
    with pytest.raises(ValidationError):
        validate_records(records, required_columns=["symbol", "ltp"], dataset_key="ds")


def test_validate_records_is_case_insensitive_on_columns():
    records = [{"Symbol": "TCS", "LTP": "10"}]
    df = validate_records(records, required_columns=["symbol", "ltp"], dataset_key="ds")
    assert len(df) == 1


def test_validate_records_drops_exact_duplicates():
    records = [
        {"symbol": "TCS", "ltp": "10"},
        {"symbol": "TCS", "ltp": "10"},
        {"symbol": "INFY", "ltp": "20"},
    ]
    df = validate_records(records, required_columns=["symbol"], dataset_key="ds")
    assert len(df) == 2
