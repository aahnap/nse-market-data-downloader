from datetime import date

from nse_downloader.cli import build_arg_parser


def test_arg_parser_defaults():
    parser = build_arg_parser()
    args = parser.parse_args([])
    assert args.datasets is None
    assert args.output_dir == "data"
    assert args.trading_date is None
    assert args.use_db is False


def test_arg_parser_single_dataset():
    parser = build_arg_parser()
    args = parser.parse_args(["--dataset", "top-gainers-losers"])
    assert args.datasets == ["top-gainers-losers"]


def test_arg_parser_multiple_datasets():
    parser = build_arg_parser()
    args = parser.parse_args(
        ["--dataset", "top-gainers-losers", "--dataset", "upper-band-hitters"]
    )
    assert args.datasets == ["top-gainers-losers", "upper-band-hitters"]


def test_arg_parser_rejects_unknown_dataset():
    parser = build_arg_parser()
    try:
        parser.parse_args(["--dataset", "not-a-real-dataset"])
        assert False, "should have raised SystemExit"
    except SystemExit:
        pass


def test_arg_parser_custom_date_and_output_dir():
    parser = build_arg_parser()
    args = parser.parse_args(["--date", "2026-09-15", "--output-dir", "/tmp/out"])
    assert args.trading_date == "2026-09-15"
    assert args.output_dir == "/tmp/out"
