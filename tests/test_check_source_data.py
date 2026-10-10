import csv
import json
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb
import pytest

from scripts.check_source_data import (
    find_latest_complete_date,
    list_source_partitions,
    load_stock_pool,
    main,
    symbols_for_date,
    validate_stock_list,
)


FIELDS = ["symbol", "name", "sector", "source_industry", "exchange", "list_status"]
SECTORS = ["金融", "消费", "制造", "医药", "科技"]
SYMBOLS = [f"{i:06d}.SH" for i in range(1, 21)]
DAILY_DATASET = "stock_daily_kbar"
MINUTE_DATASET = "stock_1min_kbar"


def stock_rows(symbols=SYMBOLS):
    return [
        {
            "symbol": symbol,
            "name": f"证券{i}",
            "sector": SECTORS[i // 4],
            "source_industry": f"行业{i // 4}",
            "exchange": "SSE",
            "list_status": "L",
        }
        for i, symbol in enumerate(symbols)
    ]


def write_stock_pool(path: Path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_parquet(path: Path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    try:
        definitions = ", ".join(f'"{column}" {kind}' for column, kind in columns)
        connection.execute(f"CREATE TABLE data ({definitions})")
        if rows:
            placeholders = ", ".join("?" for _ in columns)
            connection.executemany(
                f"INSERT INTO data VALUES ({placeholders})",
                [tuple(row.get(column) for column, _ in columns) for row in rows],
            )
        escaped_path = str(path).replace("'", "''")
        connection.execute(f"COPY data TO '{escaped_path}' (FORMAT PARQUET)")
    finally:
        connection.close()
    return path


def write_daily_partition(root, trading_date, symbols):
    return write_parquet(
        root / DAILY_DATASET / f"date={trading_date}" / "part.parquet",
        [{"symbol": symbol, "volume": 1000, "amount": 25000.0} for symbol in symbols],
        [("symbol", "VARCHAR"), ("volume", "BIGINT"), ("amount", "DOUBLE")],
    )


def write_minute_partition(root, trading_date, symbols):
    return write_parquet(
        root / MINUTE_DATASET / f"date={trading_date}" / "part.parquet",
        [{"symbol": symbol, "volume": 10} for symbol in symbols],
        [("symbol", "VARCHAR"), ("volume", "BIGINT")],
    )


def write_stock_list(root, rows):
    return write_parquet(
        root / "stock_list" / "part.parquet",
        rows,
        [("symbol", "VARCHAR"), ("list_status", "VARCHAR")],
    )


def test_load_stock_pool_requires_exactly_twenty_symbols(tmp_path):
    path = write_stock_pool(tmp_path / "stock_pool.csv", stock_rows(SYMBOLS[:19]))

    with pytest.raises(ValueError, match="20"):
        load_stock_pool(path)


def test_load_stock_pool_rejects_duplicate_symbols(tmp_path):
    rows = stock_rows()
    rows[-1]["symbol"] = rows[0]["symbol"]
    path = write_stock_pool(tmp_path / "stock_pool.csv", rows)

    with pytest.raises(ValueError, match="重复"):
        load_stock_pool(path)


def test_load_stock_pool_requires_four_symbols_per_sector(tmp_path):
    rows = stock_rows()
    rows[0]["sector"] = "消费"
    path = write_stock_pool(tmp_path / "stock_pool.csv", rows)

    with pytest.raises(ValueError, match="行业|板块|4"):
        load_stock_pool(path)


def test_load_stock_pool_requires_expected_columns(tmp_path):
    path = tmp_path / "stock_pool.csv"
    path.write_text("symbol,name\n000001.SH,示例\n", encoding="utf-8")

    with pytest.raises(ValueError, match="sector"):
        load_stock_pool(path)


def test_list_source_partitions_returns_dates_descending_and_ignores_invalid(tmp_path):
    for name in ("date=2026-01-03", "date=2026-01-01", "date=not-a-date", "other"):
        (tmp_path / "daily" / name).mkdir(parents=True)

    assert list_source_partitions(tmp_path, "daily") == [date(2026, 1, 3), date(2026, 1, 1)]


def test_symbols_for_date_reads_all_parquet_files_and_deduplicates(tmp_path):
    trading_date = date(2026, 1, 2)
    write_daily_partition(tmp_path, trading_date, SYMBOLS[:10])
    write_parquet(
        tmp_path / DAILY_DATASET / f"date={trading_date}" / "second.parquet",
        [{"symbol": symbol, "volume": 2, "amount": 5.0} for symbol in SYMBOLS[9:]],
        [("symbol", "VARCHAR"), ("volume", "BIGINT"), ("amount", "DOUBLE")],
    )

    assert symbols_for_date(tmp_path, DAILY_DATASET, trading_date, SYMBOLS) == set(SYMBOLS)


def test_find_latest_complete_date_uses_common_symbol_date(tmp_path):
    latest = date(2026, 1, 2)
    previous = date(2026, 1, 1)
    write_daily_partition(tmp_path, latest, SYMBOLS)
    write_minute_partition(tmp_path, latest, SYMBOLS[:-1])
    write_daily_partition(tmp_path, previous, SYMBOLS)
    write_minute_partition(tmp_path, previous, SYMBOLS)

    trading_date, daily_symbols, minute_symbols = find_latest_complete_date(tmp_path, SYMBOLS)

    assert trading_date == previous
    assert daily_symbols == set(SYMBOLS)
    assert minute_symbols == set(SYMBOLS)


def test_find_latest_complete_date_rejects_no_common_coverage(tmp_path):
    for index, trading_date in enumerate((date(2026, 1, 2), date(2026, 1, 1))):
        write_daily_partition(tmp_path, trading_date, SYMBOLS[:-1])
        write_minute_partition(tmp_path, trading_date, SYMBOLS if index else SYMBOLS[:-2])

    with pytest.raises(ValueError, match="共同覆盖"):
        find_latest_complete_date(tmp_path, SYMBOLS)


def test_find_latest_complete_date_requires_matching_partition_dates(tmp_path):
    trading_date = date(2026, 1, 2)
    write_daily_partition(tmp_path, trading_date, SYMBOLS)
    write_minute_partition(tmp_path, date(2026, 1, 1), SYMBOLS)

    with pytest.raises(ValueError, match="共同覆盖"):
        find_latest_complete_date(tmp_path, SYMBOLS)


def test_validate_stock_list_rejects_delisted_symbol(tmp_path):
    rows = [{"symbol": symbol, "list_status": "L"} for symbol in SYMBOLS]
    rows[-1]["list_status"] = "D"
    write_stock_list(tmp_path, rows)

    with pytest.raises(ValueError, match=SYMBOLS[-1]):
        validate_stock_list(tmp_path, SYMBOLS)


def test_validate_stock_list_rejects_missing_target_symbols(tmp_path):
    write_stock_list(tmp_path, [{"symbol": symbol, "list_status": "L"} for symbol in SYMBOLS[:-1]])

    with pytest.raises(ValueError, match=SYMBOLS[-1]):
        validate_stock_list(tmp_path, SYMBOLS)


def test_validate_stock_list_rejects_duplicate_target_rows(tmp_path):
    rows = [{"symbol": symbol, "list_status": "L"} for symbol in SYMBOLS]
    rows.append({"symbol": SYMBOLS[0], "list_status": "D"})
    write_stock_list(tmp_path, rows)

    with pytest.raises(ValueError, match=SYMBOLS[0]):
        validate_stock_list(tmp_path, SYMBOLS)


def test_main_returns_failure_for_missing_source(tmp_path, capsys):
    pool_path = write_stock_pool(tmp_path / "stock_pool.csv", stock_rows())
    missing_root = tmp_path / "missing"

    status = main(["--data-root", str(missing_root), "--stock-pool", str(pool_path)])

    captured = capsys.readouterr()
    assert status != 0
    assert str(missing_root) in captured.err


def test_main_date_does_not_fall_back_and_json_reports_missing_codes(tmp_path, capsys):
    pool_path = write_stock_pool(tmp_path / "stock_pool.csv", stock_rows())
    write_stock_list(tmp_path, [{"symbol": symbol, "list_status": "L"} for symbol in SYMBOLS])
    older = date(2026, 1, 1)
    selected = date(2026, 1, 2)
    write_daily_partition(tmp_path, older, SYMBOLS)
    write_minute_partition(tmp_path, older, SYMBOLS)
    write_daily_partition(tmp_path, selected, SYMBOLS)
    write_minute_partition(tmp_path, selected, SYMBOLS[:-1])

    status = main([
        "--data-root", str(tmp_path), "--stock-pool", str(pool_path),
        "--date", selected.isoformat(), "--format", "json",
    ])

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert status != 0
    assert report["date"] == selected.isoformat()
    assert report["missing_minute"] == [SYMBOLS[-1]]


def test_main_text_reports_counts_aggregates_and_complete_date(tmp_path, capsys):
    pool_path = write_stock_pool(tmp_path / "stock_pool.csv", stock_rows())
    write_stock_list(tmp_path, [{"symbol": symbol, "list_status": "L"} for symbol in SYMBOLS])
    trading_date = date(2026, 1, 2)
    write_daily_partition(tmp_path, trading_date, SYMBOLS)
    write_minute_partition(tmp_path, trading_date, SYMBOLS)

    status = main(["--data-root", str(tmp_path), "--stock-pool", str(pool_path)])

    captured = capsys.readouterr()
    assert status == 0
    assert "股票池数量：20" in captured.out
    assert "list_status=L 数量：20" in captured.out
    assert "共同覆盖日期：2026-01-02" in captured.out
    assert "日线成交量" in captured.out
    assert "日线成交额" in captured.out
    assert "分钟记录数" in captured.out
    assert "缺失代码（日线）：无" in captured.out
    assert "缺失代码（分钟）：无" in captured.out
