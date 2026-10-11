from __future__ import annotations

from datetime import date, datetime, time
from time import sleep
from typing import Any, Callable

import pandas as pd


class DataProviderError(RuntimeError):
    """Raised when a market data request fails after all retries."""


def _daily_date(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    return value.replace("-", "")


def _minute_datetime(value: date | datetime | str, *, end: bool = False) -> str:
    if isinstance(value, datetime):
        resolved = value
    elif isinstance(value, date):
        resolved = datetime.combine(value, time.max if end else time.min)
    else:
        resolved = datetime.fromisoformat(value)
    return resolved.strftime("%Y-%m-%d %H:%M:%S")


def _market_symbol(symbol: str) -> str:
    return f"sh{symbol}" if symbol.startswith(("6", "9")) else f"sz{symbol}"


def _rename_daily_columns(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rename(
        columns={
            "date": "日期",
            "open": "开盘",
            "close": "收盘",
            "high": "最高",
            "low": "最低",
            "volume": "成交量",
            "amount": "成交额",
        }
    )


def _rename_minute_columns(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rename(
        columns={
            "day": "时间",
            "open": "开盘",
            "close": "收盘",
            "high": "最高",
            "low": "最低",
            "volume": "成交量",
            "amount": "成交额",
        }
    )


class AkShareProvider:
    """Small boundary around the AkShare functions used by the importer."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        max_retries: int = 2,
        timeout: float = 20,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries 不能小于 0")
        if timeout <= 0:
            raise ValueError("timeout 必须大于 0")
        if client is None:
            import akshare as client

        self._client = client
        self._max_retries = max_retries
        self._timeout = timeout
        self._sleep = sleep_fn

    def fetch_daily(
        self,
        symbol: str,
        start_date: date | datetime | str,
        end_date: date | datetime | str,
    ) -> pd.DataFrame:
        kwargs = {
            "symbol": _market_symbol(symbol),
            "start_date": _daily_date(start_date),
            "end_date": _daily_date(end_date),
            "adjust": "",
            "timeout": self._timeout,
        }
        frame = self._call("日线", symbol, self._client.stock_zh_a_hist_tx, kwargs)
        return _rename_daily_columns(frame)

    def fetch_minute(
        self,
        symbol: str,
        start_datetime: date | datetime | str,
        end_datetime: date | datetime | str,
    ) -> pd.DataFrame:
        kwargs = {
            "symbol": _market_symbol(symbol),
            "period": "1",
            "adjust": "",
        }
        frame = self._call("分钟线", symbol, self._client.stock_zh_a_minute, kwargs)
        frame = _rename_minute_columns(frame)
        if frame.empty:
            return frame
        timestamps = pd.to_datetime(frame["时间"])
        start = pd.Timestamp(_minute_datetime(start_datetime))
        end = pd.Timestamp(_minute_datetime(end_datetime, end=True))
        return frame.loc[(timestamps >= start) & (timestamps <= end)].reset_index(drop=True)

    def _call(
        self,
        label: str,
        symbol: str,
        function: Callable[..., pd.DataFrame],
        kwargs: dict[str, Any],
    ) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return function(**kwargs)
            except Exception as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                self._sleep(attempt + 1)

        raise DataProviderError(
            f"{label}请求失败: symbol={symbol}, retries={self._max_retries}"
        ) from last_error
