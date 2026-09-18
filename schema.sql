-- ---------------------------------------------------------------------------
-- SQLite schema for the optional history database (enabled with --use-db).
--
-- This file is a human-readable reference copy of the schema that
-- nse_downloader/storage.py creates automatically at runtime (see the
-- `_SCHEMA` constant and `init_db()` in that file). You do not need to run
-- this file by hand -- it's here purely as a documented deliverable, and to
-- let anyone inspect the schema without reading Python.
--
-- Design notes:
--   * One row per (dataset, trading_date, individual record) rather than a
--     table per dataset, since all four datasets are conceptually
--     "a snapshot of rows for a dataset on a given day" and this keeps
--     queries across datasets simple (e.g. "show me everything from
--     2026-09-18").
--   * `row_json` stores the full row as JSON rather than fixed columns,
--     because each of the 4 datasets has a different, and occasionally
--     changing, set of fields (see README > How data acquisition works).
--     This avoids needing a schema migration every time NSE adds/renames
--     a field.
--   * The UNIQUE constraint on (dataset_key, trading_date, row_hash) is
--     what makes re-running the app safe: inserting the exact same row
--     for the same dataset/day a second time is silently ignored rather
--     than creating a duplicate (see README > How duplicate data is
--     handled).
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dataset_rows (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_key   TEXT NOT NULL,                  -- e.g. 'top-gainers-losers'
    trading_date  TEXT NOT NULL,                  -- 'YYYY-MM-DD'
    row_hash      TEXT NOT NULL,                  -- sha256 of row_json, for de-dup
    row_json      TEXT NOT NULL,                  -- the full row, as JSON
    inserted_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (dataset_key, trading_date, row_hash)
);

CREATE INDEX IF NOT EXISTS idx_dataset_date
    ON dataset_rows (dataset_key, trading_date);

-- Example queries you can run against data/nse_history.db:

-- All rows downloaded for a specific dataset and day:
--   SELECT row_json FROM dataset_rows
--   WHERE dataset_key = 'top-gainers-losers' AND trading_date = '2026-09-18';

-- How many rows have been recorded per dataset overall:
--   SELECT dataset_key, COUNT(*) FROM dataset_rows GROUP BY dataset_key;

-- Every distinct trading day we have data for:
--   SELECT DISTINCT trading_date FROM dataset_rows ORDER BY trading_date;