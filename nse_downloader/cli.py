"""
Command-line interface.

Examples
--------
    python main.py
    python main.py --dataset top-gainers-losers
    python main.py --dataset top-gainers-losers --dataset upper-band-hitters
    python main.py --output-dir /tmp/nse_data --use-db
    python main.py --date 2026-09-15
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime

from .config_loader import load_config
from .logging_setup import setup_logging
from .pipeline import run_all

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = "data"
DEFAULT_LOG_DIR = "logs"
DEFAULT_DB_PATH = "data/nse_history.db"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download NSE market-data CSVs (gainers/losers, "
        "upper band hitters, volume spurts, 52-week highs)."
    )
    parser.add_argument(
        "--dataset",
        action="append",
        dest="datasets",
        choices=[
            "top-gainers-losers",
            "upper-band-hitters",
            "volume-gainers-spurts",
            "52-week-high",
        ],
        help="Download only this dataset. Can be passed multiple times. "
        "Default: download all four.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to save CSVs into (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--date",
        dest="trading_date",
        default=None,
        help="Trading date (YYYY-MM-DD) to label files with. Default: today.",
    )
    parser.add_argument(
        "--use-db",
        action="store_true",
        help=f"Also record rows into a SQLite history DB (default path: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database file (implies --use-db).",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a custom datasets.yaml (default: bundled config/datasets.yaml)",
    )
    parser.add_argument(
        "--log-dir",
        default=DEFAULT_LOG_DIR,
        help=f"Directory to write logs into (default: {DEFAULT_LOG_DIR})",
    )
    return parser


def main(argv=None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    setup_logging(args.log_dir)

    if args.trading_date:
        try:
            trading_date = datetime.strptime(args.trading_date, "%Y-%m-%d").date()
        except ValueError:
            logger.error("Invalid --date value %r, expected YYYY-MM-DD", args.trading_date)
            return 2
    else:
        trading_date = date.today()

    config = load_config(args.config) if args.config else load_config()

    db_path = args.db_path if (args.use_db or args.db_path != DEFAULT_DB_PATH) else None

    logger.info(
        "Starting NSE downloader run for trading date %s (datasets=%s)",
        trading_date.isoformat(),
        args.datasets or "ALL",
    )

    results = run_all(
        config=config,
        output_dir=args.output_dir,
        trading_date=trading_date,
        db_path=db_path,
        dataset_keys=args.datasets,
    )

    failures = [r for r in results if not r.success]
    for r in results:
        status = "OK" if r.success else "FAILED"
        print(f"{r.dataset_key:25s} {status:8s} rows={r.row_count:<6} {r.error or ''}")

    # Non-zero exit code if *everything* failed, so cron/schedulers can
    # detect a total outage. Partial failure still exits 0 because the
    # requirement is that partial failure shouldn't be treated as fatal.
    if failures and len(failures) == len(results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
