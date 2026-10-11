from scripts.import_market_data import build_parser

import pandas as pd
from sqlalchemy import create_engine, func, select

from app import db
from app.models import Base, DailyQuote
from scripts import import_market_data as cli


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


def test_daily_cli_imports_without_exporting_database_url(tmp_path, monkeypatch, capsys):
    url = f"sqlite:///{tmp_path / 'quotes.db'}"
    env_file = tmp_path / '.env'
    env_file.write_text(f'DATABASE_URL={url}\n')
    monkeypatch.setattr(db, 'PROJECT_ENV_FILE', env_file)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    engine = create_engine(url)
    Base.metadata.create_all(engine)

    class FixtureProvider:
        def fetch_daily(self, symbol, start_date, end_date):
            return pd.DataFrame([{
                '日期': '2024-01-02', '开盘': 10, '收盘': 11,
                '最高': 12, '最低': 9, '成交量': 100, '成交额': 1000,
            }])

    monkeypatch.setattr(cli, 'AkShareProvider', FixtureProvider)
    cli.main(['daily', '--start-date', '2024-01-01', '--end-date', '2024-01-31'])

    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(DailyQuote)) == 20
    assert '新增行数=20' in capsys.readouterr().out
    engine.dispose()
