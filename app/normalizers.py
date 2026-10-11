from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import pandas as pd


def _decimal(value: Any, places: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _validate_price_range(high: Decimal, low: Decimal) -> None:
    if high < low:
        raise ValueError("最高价不能低于最低价")


def _validate_measurements(
    open_price: Decimal,
    high: Decimal,
    low: Decimal,
    close: Decimal,
    volume: int,
    amount: Decimal,
) -> None:
    if any(price <= 0 for price in (open_price, high, low, close)):
        raise ValueError("价格必须大于 0")
    if volume < 0:
        raise ValueError("成交量不能小于 0")
    if amount < 0:
        raise ValueError("成交额不能小于 0")


def normalize_daily_frame(symbol: str, frame: pd.DataFrame) -> list[dict[str, object]]:
    """Convert AkShare daily columns into database-ready quote rows."""
    required = {"日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"日线数据缺少字段: {', '.join(sorted(missing))}")

    rows: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        trade_date = pd.Timestamp(record["日期"]).date()
        if not isinstance(trade_date, date):
            raise ValueError(f"无效交易日期: {record['日期']}")
        high = _decimal(record["最高"], "0.0001")
        low = _decimal(record["最低"], "0.0001")
        open_price = _decimal(record["开盘"], "0.0001")
        close = _decimal(record["收盘"], "0.0001")
        volume = int(record["成交量"])
        amount = _decimal(record["成交额"], "0.01")
        _validate_price_range(high, low)
        _validate_measurements(open_price, high, low, close, volume, amount)
        rows.append(
            {
                "symbol": symbol,
                "trade_date": trade_date,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": amount,
            }
        )
    return rows


def normalize_minute_frame(symbol: str, frame: pd.DataFrame) -> list[dict[str, object]]:
    """Convert AkShare one-minute columns into database-ready quote rows."""
    required = {"时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"分钟数据缺少字段: {', '.join(sorted(missing))}")

    rows: list[dict[str, object]] = []
    for record in frame.to_dict(orient="records"):
        trade_time = pd.Timestamp(record["时间"]).to_pydatetime().replace(tzinfo=None)
        if not isinstance(trade_time, datetime):
            raise ValueError(f"无效交易时间: {record['时间']}")
        high = _decimal(record["最高"], "0.0001")
        low = _decimal(record["最低"], "0.0001")
        open_price = _decimal(record["开盘"], "0.0001")
        close = _decimal(record["收盘"], "0.0001")
        volume = int(record["成交量"])
        amount = _decimal(record["成交额"], "0.01")
        _validate_price_range(high, low)
        _validate_measurements(open_price, high, low, close, volume, amount)
        rows.append(
            {
                "symbol": symbol,
                "trade_time": trade_time,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": amount,
            }
        )
    return rows
