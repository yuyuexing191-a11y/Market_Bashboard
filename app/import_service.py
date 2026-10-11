from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from collections import Counter
from typing import Callable, Iterable, Protocol

import pandas as pd
from sqlalchemy.orm import Session, sessionmaker

from app.models import DailyQuote, MinuteQuote, Stock
from app.normalizers import normalize_daily_frame, normalize_minute_frame


EXPECTED_COLUMNS = (
    "symbol",
    "name",
    "sector",
    "source_industry",
    "exchange",
    "list_status",
)
EXPECTED_SECTOR_COUNTS = {
    "金融": 4,
    "消费": 4,
    "制造": 4,
    "医药": 4,
    "科技": 4,
}


@dataclass(frozen=True)
class StockPoolEntry:
    symbol: str
    name: str
    sector: str
    source_industry: str
    exchange: str
    list_status: str

    @property
    def akshare_symbol(self) -> str:
        return self.symbol.split(".", 1)[0]


@dataclass(frozen=True)
class ImportReport:
    stock_count: int
    inserted_count: int
    start: date | datetime
    end: date | datetime
    common_minute_date: date | None = None


class DailyProvider(Protocol):
    def fetch_daily(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame: ...


class MinuteProvider(Protocol):
    def fetch_minute(
        self, symbol: str, start_datetime: datetime, end_datetime: datetime
    ) -> pd.DataFrame: ...


def load_stock_pool(path: str | Path) -> list[StockPoolEntry]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise ValueError(f"股票池列必须为: {','.join(EXPECTED_COLUMNS)}")
        rows = [StockPoolEntry(**row) for row in reader]

    if len(rows) != 20:
        raise ValueError(f"股票池必须固定为 20 只，当前为 {len(rows)} 只")
    if any(not all(getattr(entry, column).strip() for column in EXPECTED_COLUMNS) for entry in rows):
        raise ValueError("股票池必填字段不能为空")
    symbols = [entry.symbol for entry in rows]
    if len(set(symbols)) != len(symbols):
        raise ValueError("股票池中存在重复 symbol")
    if any(not entry.akshare_symbol.isdigit() for entry in rows):
        raise ValueError("股票池 symbol 必须包含数字代码")
    if Counter(entry.sector for entry in rows) != EXPECTED_SECTOR_COUNTS:
        raise ValueError("股票池必须包含金融、消费、制造、医药、科技各 4 只")
    return rows


def run_daily_import(
    session_factory: sessionmaker[Session],
    provider: DailyProvider,
    pool: Iterable[StockPoolEntry],
    start_date: date,
    end_date: date,
    *,
    normalize: Callable = normalize_daily_frame,
) -> ImportReport:
    entries = list(pool)
    if not entries:
        raise ValueError("股票池不能为空")
    if start_date > end_date:
        raise ValueError("开始日期不能晚于结束日期")

    normalized_by_symbol: dict[str, list[dict]] = {}
    for entry in entries:
        frame = provider.fetch_daily(entry.akshare_symbol, start_date, end_date)
        rows = normalize(entry.akshare_symbol, frame)
        if not rows:
            raise ValueError(f"{entry.symbol} 日线数据为空")
        _reject_duplicate_keys(rows, "trade_date")
        normalized_by_symbol[entry.symbol] = rows

    inserted_count = 0
    with session_factory.begin() as session:
        _sync_stocks(session, entries)
        for entry in entries:
            for row in normalized_by_symbol[entry.symbol]:
                row["symbol"] = entry.symbol
                key = (row["symbol"], row["trade_date"])
                if session.get(DailyQuote, key) is None:
                    session.add(DailyQuote(**row))
                    inserted_count += 1
    return ImportReport(len(entries), inserted_count, start_date, end_date)


def run_minute_import(
    session_factory: sessionmaker[Session],
    provider: MinuteProvider,
    pool: Iterable[StockPoolEntry],
    start_datetime: datetime,
    end_datetime: datetime,
    *,
    normalize: Callable = normalize_minute_frame,
) -> ImportReport:
    entries = list(pool)
    if not entries:
        raise ValueError("股票池不能为空")
    if start_datetime > end_datetime:
        raise ValueError("开始时间不能晚于结束时间")

    rows_by_symbol: dict[str, list[dict]] = {}
    common_dates: set[date] | None = None
    dates_by_symbol: dict[str, set[date]] = {}
    for entry in entries:
        frame = provider.fetch_minute(
            entry.akshare_symbol, start_datetime, end_datetime
        )
        rows = normalize(entry.akshare_symbol, frame)
        _reject_duplicate_keys(rows, "trade_time")
        rows_by_symbol[entry.symbol] = rows
        dates = {row["trade_time"].date() for row in rows}
        dates_by_symbol[entry.symbol] = dates
        common_dates = dates if common_dates is None else common_dates & dates

    if not common_dates:
        missing = list(dates_by_symbol)
        raise ValueError(f"20 只股票没有共同交易日，缺少数据: {','.join(missing)}")
    latest_date = max(common_dates)

    inserted_count = 0
    with session_factory.begin() as session:
        _sync_stocks(session, entries)
        for entry in entries:
            for row in rows_by_symbol[entry.symbol]:
                if row["trade_time"].date() != latest_date:
                    continue
                row["symbol"] = entry.symbol
                key = (row["symbol"], row["trade_time"])
                if session.get(MinuteQuote, key) is None:
                    session.add(MinuteQuote(**row))
                    inserted_count += 1
    return ImportReport(
        len(entries), inserted_count, start_datetime, end_datetime, latest_date
    )


def _reject_duplicate_keys(rows: list[dict], key_name: str) -> None:
    keys = [row[key_name] for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError(f"行情数据存在重复 {key_name}")


def _sync_stocks(session: Session, entries: Iterable[StockPoolEntry]) -> None:
    for entry in entries:
        stock = session.get(Stock, entry.symbol)
        if stock is None:
            stock = Stock(symbol=entry.symbol)
            session.add(stock)
        stock.name = entry.name
        stock.sector = entry.sector
        stock.source_industry = entry.source_industry
        stock.exchange = entry.exchange
        stock.list_status = entry.list_status
