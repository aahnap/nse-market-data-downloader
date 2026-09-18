"""
Validation layer.

Responsible for answering one question: "is this data actually safe to
save?" Nothing here touches the network or the filesystem, which makes it
trivial to unit test with plain Python lists/dicts.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

import pandas as pd

from .exceptions import UnexpectedFormatError, ValidationError

logger = logging.getLogger(__name__)


def validate_records(
    records: List[Dict[str, Any]],
    required_columns: List[str],
    dataset_key: str,
) -> pd.DataFrame:
    """
    Validate raw records and return a cleaned DataFrame.

    Checks performed:
      1. The payload isn't empty.
      2. It's actually a list of dicts (a sane "table" shape).
      3. All required_columns are present (case-insensitive match, since
         NSE's field naming/casing has changed between endpoints before).
      4. Drops fully-duplicate rows.

    Raises ValidationError / UnexpectedFormatError with a message that
    ends up straight in the logs, rather than a generic pandas traceback.
    """
    if records is None:
        raise UnexpectedFormatError(f"[{dataset_key}] No data found in response")

    if not isinstance(records, list):
        raise UnexpectedFormatError(
            f"[{dataset_key}] Expected a list of records, got {type(records).__name__}"
        )

    if len(records) == 0:
        raise ValidationError(f"[{dataset_key}] Response contained zero rows")

    if not all(isinstance(r, dict) for r in records):
        raise UnexpectedFormatError(
            f"[{dataset_key}] Expected each record to be an object/dict"
        )

    df = pd.DataFrame.from_records(records)

    if df.empty:
        raise ValidationError(f"[{dataset_key}] DataFrame is empty after parsing")

    # Case-insensitive column presence check.
    lower_cols = {c.lower(): c for c in df.columns}
    missing = [c for c in required_columns if c.lower() not in lower_cols]
    if missing:
        raise ValidationError(
            f"[{dataset_key}] Missing expected column(s) {missing}. "
            f"Columns present: {list(df.columns)}"
        )

    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    removed = before - len(df)
    if removed:
        logger.info("[%s] Dropped %d exact-duplicate row(s)", dataset_key, removed)

    return df
