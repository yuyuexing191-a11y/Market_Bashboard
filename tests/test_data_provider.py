from datetime import date, datetime

import pandas as pd
import pytest

from app.data_provider import AkShareProvider, DataProviderError


class FakeAkShare:
    def __init__(self, daily_results=None, minute_results=None):
        self.daily_results = list(daily_results or [])
        self.minute_results = list(minute_results or [])
        self.daily_calls = []
        self.minute_calls = []

    def stock_zh_a_hist_tx(self, **kwargs):
        self.daily_calls.append(kwargs)
        result = self.daily_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def stock_zh_a_minute(self, **kwargs):
        self.minute_calls.append(kwargs)
        result = self.minute_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_daily_provider_uses_unadjusted_akshare_history_arguments():
    fake = FakeAkShare(daily_results=[pd.DataFrame()])
    provider = AkShareProvider(client=fake, sleep_fn=lambda _: None)

    result = provider.fetch_daily("000001", date(2024, 1, 1), date(2024, 1, 31))

    assert result.empty
    assert fake.daily_calls == [
        {
            "symbol": "sz000001",
            "start_date": "20240101",
            "end_date": "20240131",
            "adjust": "",
            "timeout": 20,
        }
    ]


def test_minute_provider_uses_one_minute_unadjusted_history_arguments():
    fake = FakeAkShare(minute_results=[pd.DataFrame()])
    provider = AkShareProvider(client=fake, sleep_fn=lambda _: None)

    result = provider.fetch_minute(
        "600000",
        datetime(2024, 1, 2, 9, 30),
        datetime(2024, 1, 2, 15, 0),
    )

    assert result.empty
    assert fake.minute_calls == [
        {
            "symbol": "sh600000",
            "period": "1",
            "adjust": "",
        }
    ]


def test_provider_maps_tencent_and_sina_columns_to_normalizer_columns():
    fake = FakeAkShare(
        daily_results=[
            pd.DataFrame(
                [{"date": "2024-01-02", "open": 1, "close": 2, "high": 3, "low": 1, "volume": 4, "amount": 5}]
            )
        ],
        minute_results=[
            pd.DataFrame(
                [{"day": "2024-01-02 09:30:00", "open": 1, "close": 2, "high": 3, "low": 1, "volume": 4, "amount": 5}]
            )
        ],
    )
    provider = AkShareProvider(client=fake, sleep_fn=lambda _: None)

    daily = provider.fetch_daily("600000", date(2024, 1, 1), date(2024, 1, 3))
    minute = provider.fetch_minute(
        "600000", datetime(2024, 1, 2, 9, 0), datetime(2024, 1, 2, 10, 0)
    )

    assert set(["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]).issubset(daily.columns)
    assert set(["时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额"]).issubset(minute.columns)


def test_provider_retries_twice_then_returns_data():
    fake = FakeAkShare(
        daily_results=[RuntimeError("temporary"), RuntimeError("temporary"), pd.DataFrame()]
    )
    provider = AkShareProvider(client=fake, sleep_fn=lambda _: None)

    result = provider.fetch_daily("000001", date(2024, 1, 1), date(2024, 1, 2))

    assert result.empty
    assert len(fake.daily_calls) == 3


def test_provider_raises_after_two_retries():
    fake = FakeAkShare(
        daily_results=[RuntimeError("one"), RuntimeError("two"), RuntimeError("three")]
    )
    provider = AkShareProvider(client=fake, sleep_fn=lambda _: None)

    with pytest.raises(DataProviderError, match="000001"):
        provider.fetch_daily("000001", date(2024, 1, 1), date(2024, 1, 2))

    assert len(fake.daily_calls) == 3
