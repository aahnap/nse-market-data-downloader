"""
Extraction: turn "whatever JSON NSE gave us" into a flat list[dict] of rows.

NSE's internal JSON APIs nest the actual table rows a few levels deep
(e.g. under `{"NIFTY": {"data": [...]}, "allSec": {"data": [...]}, ...}`)
and the exact nesting has been known to shift over time. Rather than
hardcode one brittle path per dataset, `find_record_lists` walks the whole
structure and collects every list-of-dicts it finds, and the caller picks
the most appropriate one(s). This is what lets requirement #5 ("handle
... unexpected response formats") be more than just a try/except.
"""
from __future__ import annotations

from typing import Any, Dict, List


def find_record_lists(node: Any, path: str = "") -> List[Dict[str, Any]]:
    """
    Recursively find every list of dicts inside `node`.

    Returns a list of (path, records) style entries flattened into just
    the record lists, ordered as encountered (depth-first).
    """
    found: List[Dict[str, Any]] = []

    if isinstance(node, dict):
        # Is this dict itself a "container" like {"data": [...]}?
        for key, value in node.items():
            if isinstance(value, list) and value and all(
                isinstance(item, dict) for item in value
            ):
                found.append({"path": f"{path}.{key}".lstrip("."), "records": value})
            else:
                found.extend(find_record_lists(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found.extend(find_record_lists(item, f"{path}[{i}]"))

    return found


def largest_record_list(raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback strategy: pick the biggest list-of-dicts found anywhere."""
    candidates = find_record_lists(raw_json)
    if not candidates:
        return []
    best = max(candidates, key=lambda c: len(c["records"]))
    return best["records"]


def extract_simple(raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generic extraction for single-endpoint datasets (upper-band-hitters,
    volume-gainers-spurts, 52-week-high): just take the largest
    list-of-dicts in the payload.
    """
    return largest_record_list(raw_json)


def extract_gainers_losers(
    gainers_json: Dict[str, Any], losers_json: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Combine the two top-gainers-losers API calls into one dataset, tagging
    each row with a `category` column so the CSV still maps to the single
    "Top Gainers / Losers" page.
    """
    rows: List[Dict[str, Any]] = []
    for category, payload in (("GAINER", gainers_json), ("LOSER", losers_json)):
        for record in largest_record_list(payload):
            row = dict(record)
            row["category"] = category
            rows.append(row)
    return rows
