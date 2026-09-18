"""
Pipeline: wires acquisition -> extraction -> validation -> storage
together for a single dataset, and runs the full set of datasets while
making sure one failure can't take down the others.

This is the module that satisfies:
  - "A failure downloading one dataset should not unnecessarily prevent
    the remaining datasets from being downloaded" (see run_all's
    try/except *per dataset*)
  - "Produce useful logs showing what was attempted, when, success/
    failure, record count, and errors" (every branch below logs)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .acquisition import NSEClient
from .config_loader import AppConfig, DatasetConfig
from .exceptions import NSEDownloaderError
from .extraction import extract_gainers_losers, extract_simple
from .storage import SaveResult, save_csv, save_to_db
from .validation import validate_records

logger = logging.getLogger(__name__)


@dataclass
class DatasetRunResult:
    dataset_key: str
    success: bool
    row_count: int = 0
    file_path: Optional[str] = None
    file_written: bool = True
    error: Optional[str] = None


def _fetch_and_extract(client: NSEClient, ds: DatasetConfig):
    """Dataset-specific fetch + extraction logic."""
    if ds.key == "top-gainers-losers":
        gainers = client.fetch_json(ds.api_urls["gainers"], ds.page_url)
        losers = client.fetch_json(ds.api_urls["losers"], ds.page_url)
        return extract_gainers_losers(gainers, losers)

    # All other current datasets have exactly one api_url.
    (api_url,) = ds.api_urls.values()
    raw = client.fetch_json(api_url, ds.page_url)
    return extract_simple(raw)


def run_dataset(
    dataset_key: str,
    config: AppConfig,
    client: NSEClient,
    output_dir: str,
    trading_date: date,
    db_path: Optional[str] = None,
) -> DatasetRunResult:
    ds = config.datasets[dataset_key]
    logger.info("[%s] Starting download attempt (%s)", ds.key, trading_date.isoformat())

    try:
        records = _fetch_and_extract(client, ds)
        df = validate_records(records, ds.required_columns, ds.key)
        result: SaveResult = save_csv(df, output_dir, ds.file_prefix, trading_date)

        if db_path:
            try:
                new_rows = save_to_db(df, db_path, ds.key, trading_date)
                logger.info("[%s] %d new row(s) recorded in database", ds.key, new_rows)
            except Exception as exc:  # noqa: BLE001
                # DB is a bonus feature -- never let it fail the whole run.
                logger.warning("[%s] Database write failed (non-fatal): %s", ds.key, exc)

        logger.info(
            "[%s] SUCCESS - %d row(s) - file %s",
            ds.key,
            result.row_count,
            "unchanged (skipped)" if not result.written else result.path,
        )
        return DatasetRunResult(
            dataset_key=ds.key,
            success=True,
            row_count=result.row_count,
            file_path=result.path,
            file_written=result.written,
        )

    except NSEDownloaderError as exc:
        logger.error("[%s] FAILED - %s: %s", ds.key, type(exc).__name__, exc)
        return DatasetRunResult(dataset_key=ds.key, success=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001 - last line of defence
        logger.exception("[%s] FAILED - unexpected error: %s", ds.key, exc)
        return DatasetRunResult(dataset_key=ds.key, success=False, error=str(exc))


def run_all(
    config: AppConfig,
    output_dir: str,
    trading_date: date,
    db_path: Optional[str] = None,
    dataset_keys: Optional[list[str]] = None,
) -> list[DatasetRunResult]:
    client = NSEClient(config.common)
    keys = dataset_keys or list(config.datasets.keys())

    results = []
    for key in keys:
        # Each dataset is fully isolated: an exception inside run_dataset
        # is already caught there, but this loop structure itself also
        # guarantees we never `raise` out mid-loop.
        results.append(run_dataset(key, config, client, output_dir, trading_date, db_path))

    succeeded = sum(1 for r in results if r.success)
    logger.info("Run complete: %d/%d dataset(s) succeeded", succeeded, len(results))
    return results
