from scripts.import_market_data import build_parser


def test_daily_command_requires_explicit_date_range():
    parser = build_parser()

    args = parser.parse_args(
        ["daily", "--start-date", "2024-01-01", "--end-date", "2024-01-31"]
    )

    assert args.command == "daily"
    assert args.start_date.isoformat() == "2024-01-01"
    assert args.end_date.isoformat() == "2024-01-31"


def test_minute_command_has_recent_window_default():
    parser = build_parser()

    args = parser.parse_args(["minute"])

    assert args.command == "minute"
    assert args.lookback_days == 5
