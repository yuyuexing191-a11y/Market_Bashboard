from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import pytest

from app.normalizers import normalize_daily_frame, normalize_minute_frame


def test_normalize_daily_frame_maps_akshare_columns_to_daily_quote_rows() -> None:
    frame = pd.DataFrame(
        [
            {
                "日期": "2026-10-09",
                "开盘": 10.0,
                "收盘": 10.2,
                "最高": 10.5,
                "最低": 9.8,
                "成交量": 1000,
                "成交额": 10200.0,
            }
        ]
    )

    rows = normalize_daily_frame("600519.SH", frame)

    assert rows == [
        {
            "symbol": "600519.SH",
            "trade_date": date(2026, 10, 9),
            "open": Decimal("10.0000"),
            "high": Decimal("10.5000"),
            "low": Decimal("9.8000"),
            "close": Decimal("10.2000"),
            "volume": 1000,
            "amount": Decimal("10200.00"),
        }
    ]


def test_normalize_minute_frame_maps_akshare_columns_to_minute_quote_rows() -> None:
    frame = pd.DataFrame(
        [
            {
                "时间": "2026-10-09 09:30:00",
                "开盘": 10.0,
                "收盘": 10.2,
                "最高": 10.5,
                "最低": 9.8,
                "成交量": 1000,
                "成交额": 10200.0,
                "均价": 10.1,
            }
        ]
    )

    rows = normalize_minute_frame("600519.SH", frame)

    assert rows == [
        {
            "symbol": "600519.SH",
            "trade_time": datetime(2026, 10, 9, 9, 30),
            "open": Decimal("10.0000"),
            "high": Decimal("10.5000"),
            "low": Decimal("9.8000"),
            "close": Decimal("10.2000"),
            "volume": 1000,
            "amount": Decimal("10200.00"),
        }
    ]


def test_normalize_daily_frame_rejects_high_below_low() -> None:
    frame = pd.DataFrame(
        [
            {
                "日期": "2026-10-09",
                "开盘": 10.0,
                "收盘": 9.0,
                "最高": 8.0,
                "最低": 9.5,
                "成交量": 1000,
                "成交额": 10200.0,
            }
        ]
    )

    with pytest.raises(ValueError, match="最高价不能低于最低价"):
        normalize_daily_frame("600519.SH", frame)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("开盘", 0, "价格必须大于 0"),
        ("成交量", -1, "成交量不能小于 0"),
        ("成交额", -1, "成交额不能小于 0"),
    ],
)
def test_normalize_daily_frame_rejects_invalid_measurements(column, value, message):
    row = {
        "日期": "2024-01-02",
        "开盘": 10,
        "收盘": 11,
        "最高": 12,
        "最低": 9,
        "成交量": 100,
        "成交额": 1000,
    }
    row[column] = value

    with pytest.raises(ValueError, match=message):
        normalize_daily_frame("000001", pd.DataFrame([row]))


def test_normalize_minute_frame_rejects_invalid_measurements():
    row = {
        "时间": "2024-01-02 09:30:00",
        "开盘": 10,
        "收盘": 11,
        "最高": 12,
        "最低": 9,
        "成交量": 100,
        "成交额": -1,
    }

    with pytest.raises(ValueError, match="成交额不能小于 0"):
        normalize_minute_frame("000001", pd.DataFrame([row]))
