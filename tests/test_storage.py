import os
from datetime import date

import pandas as pd

from nse_downloader.storage import save_csv, save_to_db


def test_save_csv_creates_file(tmp_path):
    df = pd.DataFrame([{"symbol": "TCS", "ltp": "100"}])
    result = save_csv(df, str(tmp_path), "top_gainers_losers", date(2026, 9, 17))

    assert result.written is True
    assert os.path.exists(result.path)
    assert "top_gainers_losers_2026-09-17.csv" in result.path


def test_save_csv_running_twice_same_day_same_data_does_not_rewrite(tmp_path):
    df = pd.DataFrame([{"symbol": "TCS", "ltp": "100"}])
    first = save_csv(df, str(tmp_path), "ds", date(2026, 9, 17))
    second = save_csv(df, str(tmp_path), "ds", date(2026, 9, 17))

    assert first.written is True
    assert second.written is False  # unchanged -> skipped
    # Still only ONE file for that dataset+day.
    files = [f for f in os.listdir(tmp_path) if f.startswith("ds_")]
    assert len(files) == 1


def test_save_csv_same_day_but_changed_data_overwrites_same_file(tmp_path):
    df1 = pd.DataFrame([{"symbol": "TCS", "ltp": "100"}])
    df2 = pd.DataFrame([{"symbol": "TCS", "ltp": "105"}])

    save_csv(df1, str(tmp_path), "ds", date(2026, 9, 17))
    result2 = save_csv(df2, str(tmp_path), "ds", date(2026, 9, 17))

    assert result2.written is True
    files = [f for f in os.listdir(tmp_path) if f.startswith("ds_")]
    assert len(files) == 1  # overwritten, not duplicated

    on_disk = pd.read_csv(result2.path)
    assert on_disk.iloc[0]["ltp"] == 105


def test_save_csv_different_days_creates_separate_files(tmp_path):
    df = pd.DataFrame([{"symbol": "TCS", "ltp": "100"}])
    r1 = save_csv(df, str(tmp_path), "ds", date(2026, 9, 17))
    r2 = save_csv(df, str(tmp_path), "ds", date(2026, 9, 18))

    assert r1.path != r2.path
    files = [f for f in os.listdir(tmp_path) if f.startswith("ds_")]
    assert len(files) == 2


def test_save_to_db_deduplicates_on_rerun(tmp_path):
    db_path = str(tmp_path / "history.db")
    df = pd.DataFrame([{"symbol": "TCS", "ltp": "100"}])

    inserted_first = save_to_db(df, db_path, "ds", date(2026, 9, 17))
    inserted_second = save_to_db(df, db_path, "ds", date(2026, 9, 17))

    assert inserted_first == 1
    assert inserted_second == 0  # identical row already present, not duplicated
