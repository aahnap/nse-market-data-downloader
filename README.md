# NSE Market Data Downloader

![Tests](https://github.com/<your-username>/<your-repo>/actions/workflows/tests.yml/badge.svg)

An automated command-line tool that downloads four NSE market-data
datasets and saves each one as a dated CSV file, without any manual
copy-pasting from the website.

Datasets covered:

| Dataset | NSE Page |
|---|---|
| `top-gainers-losers` | https://www.nseindia.com/market-data/top-gainers-losers |
| `upper-band-hitters` | https://www.nseindia.com/market-data/upper-band-hitters |
| `volume-gainers-spurts` | https://www.nseindia.com/market-data/volume-gainers-spurts |
| `52-week-high` | https://www.nseindia.com/market-data/52-week-high-equity-market |

## What it does

Each run:

1. Calls NSE's internal JSON APIs that power the four pages above (see
   *How data acquisition works*).
2. Extracts the table rows from whatever shape of JSON comes back.
3. Validates the rows (non-empty, expected columns present, duplicates
   removed).
4. Saves a CSV per dataset, named with the trading date, so re-running
   the tool doesn't create a mess of duplicate files.
5. Logs exactly what happened for every dataset, every run.

A failure in one dataset (network blip, NSE changing something, etc.)
never stops the other three from being attempted and saved.

## Architecture

```
nse_downloader/
├── config/
│   └── datasets.yaml       # URLs + expected columns per dataset (no code here)
├── nse_downloader/
│   ├── config_loader.py    # Reads datasets.yaml into typed objects
│   ├── acquisition.py      # HTTP layer: session/cookies, retries, backoff
│   ├── extraction.py       # Turns raw NSE JSON into flat row lists
│   ├── validation.py       # Checks data is safe to save (pandas)
│   ├── storage.py          # Writes CSVs + optional SQLite history
│   ├── pipeline.py         # Wires the above together, isolates failures
│   ├── exceptions.py       # Specific error types (network/HTTP/format/validation)
│   ├── logging_setup.py    # Console + rotating file logging
│   └── cli.py              # argparse entry point
├── tests/                  # pytest suite (mocks HTTP, no live network needed)
├── data/                   # Output CSVs land here (git-ignored except samples)
├── logs/                   # Rotating log files land here
├── main.py                 # `python main.py ...`
├── requirements.txt
├── pyproject.toml
└── Dockerfile
```

This follows a fairly standard pipeline separation: **acquisition** (get
raw data) → **extraction** (shape it into rows) → **validation** (is it
trustworthy) → **storage** (persist it), coordinated by a thin
**pipeline**/**cli** layer. Each module can be tested and reasoned about
independently, and `config/datasets.yaml` means adding a 5th dataset
never touches the Python code.

## Installation

Requires Python 3.10+.

```bash
git clone <this-repo>
cd nse_downloader
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## How to run it

```bash
# Download all four datasets
python main.py

# Download just one
python main.py --dataset top-gainers-losers

# Download a specific subset
python main.py --dataset top-gainers-losers --dataset 52-week-high

# Choose where files go
python main.py --output-dir /path/to/output

# Also record rows into a SQLite history database
python main.py --use-db

# Backfill / label files for a specific trading date
python main.py --date 2026-09-15
```

Exit code is `0` on full or partial success, and `1` only if *every*
dataset failed (useful for cron/monitoring to detect a total outage
without alerting on every single transient failure).

### Scheduling it (bonus: automatic execution)

Any OS scheduler works, since this is a normal CLI script. Example
crontab entry to run at 4:00 PM IST on weekdays, after markets close:

```
0 16 * * 1-5 cd /path/to/nse_downloader && /path/to/.venv/bin/python main.py >> logs/cron.log 2>&1
```

### Docker (bonus)

```bash
docker build -t nse-downloader .
docker run -v $(pwd)/data:/app/data -v $(pwd)/logs:/app/logs nse-downloader
```

## How data acquisition works

The four NSE pages render their tables from NSE's own internal JSON
endpoints (not officially documented, and occasionally changed by NSE).
Calling those endpoints directly requires imitating a browser:

1. `NSEClient` first does a plain `GET` on the NSE homepage with
   browser-like headers, purely to receive session cookies.
2. It reuses that same `requests.Session` (cookies included) to call the
   actual data endpoint, with a `Referer` header set to the relevant
   page — NSE rejects calls that don't carry this.
3. If NSE changes the endpoint URLs, only `config/datasets.yaml` needs
   updating — no code changes.

Because JSON schema/nesting has shifted before, extraction doesn't
hardcode one exact JSON path per dataset. `extraction.find_record_lists`
walks the whole JSON tree and picks up every list-of-dicts it finds; for
single-endpoint datasets we take the largest one found (the actual
table), which tolerates NSE wrapping the same data differently.

## Where files are stored

CSVs are written to `data/` (configurable via `--output-dir`) as:

```
<dataset_prefix>_<trading_date>.csv
```

e.g. `top_gainers_losers_2026-09-17.csv`. Sample output for all four
datasets (generated from realistic fixture data, since live market data
is only available during NSE trading hours) is included in `data/`.

If `--use-db` is passed, rows are also written into a SQLite database
(`data/nse_history.db` by default) in a single `dataset_rows` table, so
history across many days can be queried with plain SQL instead of
opening dozens of CSVs.

## How errors are handled

Every possible failure point raises one of these specific exceptions
(`nse_downloader/exceptions.py`), all caught per-dataset in
`pipeline.run_dataset`:

| Situation | Exception |
|---|---|
| DNS/connection failure, timeout | `NetworkError` |
| 5xx server error (retried) / 4xx client error (not retried) | `HTTPStatusError` |
| Server responded but body is empty | `EmptyResponseError` |
| Body isn't valid JSON | `InvalidResponseError` |
| JSON is valid but has no usable table in it | `UnexpectedFormatError` |
| Data present but fails validation (missing columns, empty) | `ValidationError` |

Network errors and 5xx responses are retried with exponential backoff
(`backoff_base_seconds * 2^attempt`, default 2s/4s/8s, configurable in
`datasets.yaml`). 4xx errors are not retried since retrying won't fix a
bad URL or auth issue.

Whatever the failure, `pipeline.run_dataset` catches it, logs it with the
dataset name and reason, and returns a result object — it never lets one
dataset's exception stop `run_all` from moving on to the next dataset.

## How duplicate data is handled

Two layers of de-duplication:

* **Within a dataset**: `validation.validate_records` drops exact
  duplicate rows before saving.
* **Across runs on the same day**: `storage.save_csv` names files by
  trading date, so re-running the tool targets the *same* file. If the
  new data is byte-for-byte identical to what's already saved, the write
  is skipped entirely (logged as "no changes"). If it differs (e.g. NSE's
  intraday numbers moved), the same file is overwritten with the latest
  snapshot — you never end up with `..._1.csv`, `..._2.csv` clutter.
* If `--use-db` is used, SQLite additionally enforces a
  `(dataset, trading_date, row_hash)` uniqueness constraint, so re-running
  the app never inserts duplicate history rows either.

## How tests are run

```bash
pip install -r requirements.txt   # includes pytest + responses
pytest -v
```

The suite (31 tests) covers:

* **Extraction** — pulling records out of nested/varying JSON shapes.
* **Validation** — empty data, wrong types, missing columns, dedup.
* **Storage** — file creation, same-day no-op, same-day overwrite,
  different-day separate files, SQLite dedup.
* **Acquisition** — success, retry-then-succeed on 5xx, exhausted
  retries, no-retry on 4xx, empty body, invalid JSON, network error —
  all using the `responses` library to mock HTTP, so tests need **no
  live network access** and run in well under a second.
* **Pipeline** — a failing dataset does not prevent other datasets from
  succeeding and being saved (using a fake client, no real network).
* **CLI** — argument parsing behaves as documented.

## Limitations / assumptions

* NSE's internal API endpoints and JSON field names are not officially
  documented and can change without notice. The URLs and expected
  columns are centralized in `config/datasets.yaml` specifically so they
  can be fixed in one place if NSE changes something, without touching
  application code.
* This project was verified against the live NSE site on 18 Sep 2026 — all
  four datasets downloaded successfully. Two of the four required
  config-only fixes on the first real run (the `upper-band-hitters`
  endpoint URL, and the expected columns for `volume-gainers-spurts`),
  which is exactly the scenario `config/datasets.yaml` was designed to
  isolate: both were fixed by editing that one file, with zero changes to
  application code. Same-day CSV overwrite and SQLite cross-run
  de-duplication were also confirmed live, not just in the test suite.
* NSE's internal API endpoints and JSON field names are not officially
  documented and can change without notice; if a dataset starts failing
  again, `config/datasets.yaml` is the first (and likely only) place that
  needs updating.
* No data is fetched outside Indian market hours in a special way — the
  tool will still attempt the download and simply save whatever NSE last
  had computed (typically the previous close) on weekends/holidays.
* Notifications on failure are not implemented; failures are surfaced
  via logs and a non-zero exit code when *all* datasets fail, which is
  enough for most cron/monitoring setups to alert on.