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


class AkShareProvider:
    """Small boundary around the AkShare functions used by the importer."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        max_retries: int = 2,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries 不能小于 0")
        if client is None:
            import akshare as client

        self._client = client
        self._max_retries = max_retries
        self._sleep = sleep_fn

    def fetch_daily(
        self,
        symbol: str,
        start_date: date | datetime | str,
        end_date: date | datetime | str,
    ) -> pd.DataFrame:
        kwargs = {
            "symbol": symbol,
            "period": "daily",
            "start_date": _daily_date(start_date),
            "end_date": _daily_date(end_date),
            "adjust": "",
        }
        return self._call("日线", symbol, self._client.stock_zh_a_hist, kwargs)

    def fetch_minute(
        self,
        symbol: str,
        start_datetime: date | datetime | str,
        end_datetime: date | datetime | str,
    ) -> pd.DataFrame:
        kwargs = {
            "symbol": symbol,
            "start_date": _minute_datetime(start_datetime),
            "end_date": _minute_datetime(end_datetime, end=True),
            "period": "1",
            "adjust": "",
        }
        return self._call(
            "分钟线", symbol, self._client.stock_zh_a_hist_min_em, kwargs
        )

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
