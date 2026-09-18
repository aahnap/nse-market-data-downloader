"""
Storage layer: turns a validated DataFrame into files on disk (and,
optionally, rows in a SQLite database for historical querying).

Design choices, and why:

* Filenames are `<prefix>_<trading_date>.csv` (e.g.
  `top_gainers_losers_2026-09-17.csv`). The date is *part of the name*
  rather than a timestamp suffix, so running the app twice in one day
  targets the same file instead of creating
  `..._103000.csv`, `..._154500.csv`, etc. -- this is what satisfies
  "running the application twice ... should not ... create confusing
  duplicate files".
* If that file already exists, we compare its content hash to the new
  data. Identical -> we skip the write entirely (and say so in the log).
  Different -> we overwrite it (NSE's intraday numbers do change through
  the day, so the freshest snapshot for that trading day is what should
  be on disk) but keep exactly one dated CSV per dataset per day, never
  a growing pile.
* SQLite storage is additive/optional (bonus: "Database storage in
  addition to CSV") and gives a queryable history across many days,
  using an (dataset, trading_date, row_hash) uniqueness rule so re-runs
  don't create duplicate rows there either.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SaveResult:
    path: str
    written: bool  # False if skipped because content was unchanged
    row_count: int


def _dataframe_hash(df: pd.DataFrame) -> str:
    payload = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def save_csv(
    df: pd.DataFrame,
    output_dir: str,
    file_prefix: str,
    trading_date: date,
) -> SaveResult:
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{file_prefix}_{trading_date.isoformat()}.csv"
    path = os.path.join(output_dir, filename)

    new_hash = _dataframe_hash(df)

    if os.path.exists(path):
        try:
            existing = pd.read_csv(path)
            existing_hash = _dataframe_hash(existing)
        except Exception as exc:  # noqa: BLE001 - corrupt/partial old file
            logger.warning(
                "Could not read existing file %s to compare (%s); overwriting.",
                path,
                exc,
            )
            existing_hash = None

        if existing_hash == new_hash:
            logger.info(
                "No changes for %s vs existing file; skipping re-write.", filename
            )
            return SaveResult(path=path, written=False, row_count=len(df))

        logger.info("Existing file %s differs from latest data; overwriting.", filename)

    df.to_csv(path, index=False)
    logger.info("Wrote %d row(s) to %s", len(df), path)
    return SaveResult(path=path, written=True, row_count=len(df))


# ---------------------------------------------------------------------------
# Optional SQLite history (bonus)
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dataset_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_key TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    row_hash TEXT NOT NULL,
    row_json TEXT NOT NULL,
    inserted_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(dataset_key, trading_date, row_hash)
);
CREATE INDEX IF NOT EXISTS idx_dataset_date
    ON dataset_rows (dataset_key, trading_date);
"""


def init_db(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def save_to_db(
    df: pd.DataFrame,
    db_path: str,
    dataset_key: str,
    trading_date: date,
) -> int:
    """
    Insert rows into SQLite, skipping ones already present for this
    dataset+date+content (so re-running the app doesn't duplicate rows).
    Returns the number of newly inserted rows.
    """
    init_db(db_path)
    inserted = 0
    with sqlite3.connect(db_path) as conn:
        for _, row in df.iterrows():
            row_json = row.to_json()
            row_hash = hashlib.sha256(row_json.encode("utf-8")).hexdigest()
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO dataset_rows
                    (dataset_key, trading_date, row_hash, row_json)
                VALUES (?, ?, ?, ?)
                """,
                (dataset_key, trading_date.isoformat(), row_hash, row_json),
            )
            inserted += cur.rowcount
        conn.commit()
    return inserted
