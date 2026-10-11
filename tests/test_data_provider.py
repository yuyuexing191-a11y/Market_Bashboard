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

    def stock_zh_a_hist(self, **kwargs):
        self.daily_calls.append(kwargs)
        result = self.daily_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def stock_zh_a_hist_min_em(self, **kwargs):
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
            "symbol": "000001",
            "period": "daily",
            "start_date": "20240101",
            "end_date": "20240131",
            "adjust": "",
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
            "symbol": "600000",
            "start_date": "2024-01-02 09:30:00",
            "end_date": "2024-01-02 15:00:00",
            "period": "1",
            "adjust": "",
        }
    ]


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
