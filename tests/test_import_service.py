from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.import_service import load_stock_pool, run_daily_import, run_minute_import
from app.models import Base, DailyQuote, MinuteQuote, Stock


POOL_PATH = Path(__file__).parents[1] / "config" / "stock_pool.csv"


class FakeProvider:
    def __init__(self, frames, failure=None):
        self.frames = frames
        self.failure = failure
        self.calls = []

    def fetch_daily(self, symbol, start_date, end_date):
        self.calls.append((symbol, start_date, end_date))
        if self.failure and symbol == self.failure[0]:
            raise RuntimeError(self.failure[1])
        return self.frames[symbol]


class FakeMinuteProvider:
    def __init__(self, frames, failure=None):
        self.frames = frames
        self.failure = failure
        self.calls = []

    def fetch_minute(self, symbol, start_datetime, end_datetime):
        self.calls.append((symbol, start_datetime, end_datetime))
        if self.failure and symbol == self.failure[0]:
            raise RuntimeError(self.failure[1])
        return self.frames[symbol]


def _daily_frame():
    return pd.DataFrame(
        [{
            "日期": "2024-01-02",
            "开盘": 10,
            "收盘": 11,
            "最高": 12,
            "最低": 9,
            "成交量": 100,
            "成交额": 1000,
        }]
    )


def _minute_frame(*timestamps):
    return pd.DataFrame(
        [
            {
                "时间": timestamp,
                "开盘": 10,
                "收盘": 11,
                "最高": 12,
                "最低": 9,
                "成交量": 100,
                "成交额": 1000,
            }
            for timestamp in timestamps
        ]
    )


def test_load_stock_pool_requires_exactly_twenty_rows():
    entries = load_stock_pool(POOL_PATH)

    assert len(entries) == 20
    assert entries[0].symbol == "601318.SH"
    assert entries[0].akshare_symbol == "601318"


def test_load_stock_pool_rejects_wrong_count(tmp_path):
    path = tmp_path / "pool.csv"
    path.write_text(POOL_PATH.read_text().splitlines()[0] + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="20"):
        load_stock_pool(path)


def test_load_stock_pool_rejects_blank_required_field(tmp_path):
    lines = POOL_PATH.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace("中国平安", "")
    path = tmp_path / "pool.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="必填字段"):
        load_stock_pool(path)


def test_load_stock_pool_rejects_wrong_sector_distribution(tmp_path):
    lines = POOL_PATH.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace(",金融,", ",消费,")
    path = tmp_path / "pool.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="各 4 只"):
        load_stock_pool(path)


def test_daily_import_syncs_stocks_and_skips_existing_quotes():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine)
    pool = load_stock_pool(POOL_PATH)[:1]
    provider = FakeProvider({"601318": _daily_frame()})

    first = run_daily_import(
        session_factory, provider, pool, date(2024, 1, 1), date(2024, 1, 31)
    )
    second = run_daily_import(
        session_factory, provider, pool, date(2024, 1, 1), date(2024, 1, 31)
    )

    with session_factory() as session:
        assert session.scalar(select(Stock.symbol)) == "601318.SH"
        quotes = session.scalars(select(DailyQuote)).all()
        assert len(quotes) == 1
        assert quotes[0].open == Decimal("10.0000")
    assert len(provider.calls) == 2
    assert first.inserted_count == 1
    assert second.inserted_count == 0


def test_daily_import_validates_date_range_before_network_call():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine)
    pool = load_stock_pool(POOL_PATH)[:1]
    provider = FakeProvider({"601318": _daily_frame()})

    with pytest.raises(ValueError, match="开始日期"):
        run_daily_import(
            session_factory, provider, pool, date(2024, 2, 1), date(2024, 1, 1)
        )

    assert provider.calls == []


def test_daily_import_rolls_back_stock_and_quotes_when_provider_fails():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine)
    pool = load_stock_pool(POOL_PATH)[:2]
    provider = FakeProvider(
        {"601318": _daily_frame(), "600030": _daily_frame()},
        failure=("600030", "network down"),
    )

    with pytest.raises(RuntimeError, match="network down"):
        run_daily_import(session_factory, provider, pool, date(2024, 1, 1), date(2024, 1, 31))

    with session_factory() as session:
        assert session.scalar(select(Stock.symbol)) is None
        assert session.scalar(select(DailyQuote.symbol)) is None


def test_minute_import_uses_latest_date_shared_by_all_stocks():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine)
    pool = load_stock_pool(POOL_PATH)[:2]
    provider = FakeMinuteProvider(
        {
            "601318": _minute_frame("2024-01-02 09:30:00", "2024-01-03 09:30:00"),
            "600030": _minute_frame("2024-01-02 09:30:00"),
        }
    )

    run_minute_import(
        session_factory,
        provider,
        pool,
        datetime(2024, 1, 1),
        datetime(2024, 1, 5),
    )

    with session_factory() as session:
        quotes = session.scalars(select(MinuteQuote).order_by(MinuteQuote.symbol)).all()
        assert [(quote.symbol, quote.trade_time.date()) for quote in quotes] == [
            ("600030.SH", date(2024, 1, 2)),
            ("601318.SH", date(2024, 1, 2)),
        ]


def test_minute_import_fails_and_rolls_back_when_no_common_date():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine)
    pool = load_stock_pool(POOL_PATH)[:2]
    provider = FakeMinuteProvider(
        {
            "601318": _minute_frame("2024-01-02 09:30:00"),
            "600030": _minute_frame("2024-01-03 09:30:00"),
        }
    )

    with pytest.raises(ValueError, match="共同交易日.*600030.SH"):
        run_minute_import(
            session_factory,
            provider,
            pool,
            datetime(2024, 1, 1),
            datetime(2024, 1, 5),
        )

    with session_factory() as session:
        assert session.scalar(select(Stock.symbol)) is None
        assert session.scalar(select(MinuteQuote.symbol)) is None
