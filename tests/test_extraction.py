import json
import os

from nse_downloader.extraction import (
    extract_gainers_losers,
    extract_simple,
    find_record_lists,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_find_record_lists_finds_nested_data():
    raw = load_fixture("sample_gainers.json")
    found = find_record_lists(raw)
    assert len(found) == 1
    assert found[0]["records"][0]["symbol"] == "TCS"


def test_extract_simple_returns_records():
    raw = load_fixture("sample_upper_band.json")
    records = extract_simple(raw)
    assert len(records) == 2
    assert records[0]["symbol"] == "SUZLON"


def test_extract_simple_handles_empty_payload():
    assert extract_simple({}) == []
    assert extract_simple({"data": []}) == []


def test_extract_gainers_losers_combines_and_tags_category():
    gainers = load_fixture("sample_gainers.json")
    losers = load_fixture("sample_losers.json")
    rows = extract_gainers_losers(gainers, losers)

    assert len(rows) == 3
    categories = {r["category"] for r in rows}
    assert categories == {"GAINER", "LOSER"}

    gainer_symbols = {r["symbol"] for r in rows if r["category"] == "GAINER"}
    assert gainer_symbols == {"TCS", "INFY"}


def test_find_record_lists_ignores_non_dict_lists():
    raw = {"tags": ["a", "b", "c"], "data": [{"x": 1}]}
    found = find_record_lists(raw)
    # Only the list-of-dicts should be picked up, not the list of strings.
    assert len(found) == 1
    assert found[0]["records"] == [{"x": 1}]
