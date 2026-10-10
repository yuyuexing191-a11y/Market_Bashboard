#!/usr/bin/env python3
"""Read-only checks for the configured market data source."""

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Sequence

import duckdb


STOCK_POOL_COLUMNS = {"symbol", "name", "sector", "source_industry", "exchange", "list_status"}
DAILY_DATASET = "stock_daily_kbar"
MINUTE_DATASET = "stock_1min_kbar"
STOCK_LIST_DATASET = "stock_list"


def load_stock_pool(path: Path) -> list[str]:
    """Load and validate the configured 20-symbol CSV stock pool."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            columns = set(reader.fieldnames or [])
            missing_columns = sorted(STOCK_POOL_COLUMNS - columns)
            if missing_columns:
                raise ValueError(f"股票池 {path} 缺少列: {', '.join(missing_columns)}")
            rows = list(reader)
    except OSError as exc:
        raise ValueError(f"无法读取股票池文件 {path}: {exc}") from exc

    symbols = [row["symbol"].strip() for row in rows]
    empty_rows = [str(index + 2) for index, symbol in enumerate(symbols) if not symbol]
    if empty_rows:
        raise ValueError(f"股票池 {path} 存在空代码，行号: {', '.join(empty_rows)}")

    duplicates = sorted(symbol for symbol, count in Counter(symbols).items() if count > 1)
    if duplicates:
        raise ValueError(f"股票池存在重复代码: {', '.join(duplicates)}")
    if len(symbols) != 20:
        raise ValueError(f"股票池数量必须为 20，实际为 {len(symbols)}")

    sector_counts = Counter(row["sector"].strip() for row in rows)
    invalid_sectors = sorted(sector for sector, count in sector_counts.items() if count != 4)
    if len(sector_counts) != 5 or invalid_sectors:
        details = ", ".join(f"{sector or '(空)'}={sector_counts[sector]}" for sector in sorted(sector_counts))
        raise ValueError(f"股票池要求每个行业恰好 4 只（共 5 类），实际分布: {details}")
    return symbols


def list_source_partitions(data_root: Path, dataset: str) -> list[date]:
    """List valid date partition directory names in descending order."""
    dataset_root = Path(data_root) / dataset
    if not dataset_root.is_dir():
        return []

    partitions = []
    for entry in dataset_root.iterdir():
        if not entry.is_dir() or not entry.name.startswith("date="):
            continue
        value = entry.name.removeprefix("date=")
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            continue
        if parsed.isoformat() == value:
            partitions.append(parsed)
    return sorted(partitions, reverse=True)


def _parquet_files(data_root: Path, dataset: str, trading_date: date | None = None) -> list[str]:
    location = Path(data_root) / dataset
    if trading_date is not None:
        location = location / f"date={trading_date.isoformat()}"
    files = sorted(str(path) for path in location.glob("*.parquet")) if location.is_dir() else []
    if not files:
        date_label = f" 日期 {trading_date.isoformat()}" if trading_date else ""
        raise ValueError(f"数据集 {dataset}{date_label} 没有找到 Parquet 文件: {location}")
    return files


def _require_columns(files: list[str], dataset: str, required: set[str], trading_date: date | None = None) -> None:
    with duckdb.connect() as connection:
        description = connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [files]).fetchall()
    available = {row[0] for row in description}
    missing = sorted(required - available)
    if missing:
        date_label = f" 日期 {trading_date.isoformat()}" if trading_date else ""
        raise ValueError(f"数据集 {dataset}{date_label} 缺少字段: {', '.join(missing)}")


def _target_query(files: list[str], symbols: list[str], sql: str):
    with duckdb.connect() as connection:
        return connection.execute(sql, [files, symbols]).fetchall()


def symbols_for_date(data_root: Path, dataset: str, trading_date: date, symbols: list[str]) -> set[str]:
    """Read distinct target symbols found in all Parquet files for a date."""
    files = _parquet_files(data_root, dataset, trading_date)
    _require_columns(files, dataset, {"symbol"}, trading_date)
    rows = _target_query(
        files,
        symbols,
        """SELECT DISTINCT symbol
           FROM read_parquet(?)
           WHERE symbol IN (SELECT UNNEST(?))""",
    )
    return {row[0] for row in rows if row[0] is not None}


def find_latest_complete_date(data_root: Path, symbols: list[str]) -> tuple[date, set[str], set[str]]:
    """Find the newest date where both daily and minute data cover the pool."""
    daily_dates = set(list_source_partitions(data_root, DAILY_DATASET))
    minute_dates = set(list_source_partitions(data_root, MINUTE_DATASET))
    common_dates = sorted(daily_dates & minute_dates, reverse=True)
    target_symbols = set(symbols)
    for trading_date in common_dates:
        daily_symbols = symbols_for_date(data_root, DAILY_DATASET, trading_date, symbols)
        minute_symbols = symbols_for_date(data_root, MINUTE_DATASET, trading_date, symbols)
        if daily_symbols >= target_symbols and minute_symbols >= target_symbols:
            return trading_date, daily_symbols, minute_symbols
    raise ValueError("没有日线与分钟数据都完整覆盖股票池的共同覆盖日期")


def validate_stock_list(data_root: Path, symbols: list[str]) -> set[str]:
    """Require each target stock to occur once in stock_list and be listed."""
    files = _parquet_files(data_root, STOCK_LIST_DATASET)
    _require_columns(files, STOCK_LIST_DATASET, {"symbol", "list_status"})
    rows = _target_query(
        files,
        symbols,
        """SELECT symbol, list_status, COUNT(*) AS row_count
           FROM read_parquet(?)
           WHERE symbol IN (SELECT UNNEST(?))
           GROUP BY symbol, list_status""",
    )
    status_by_symbol: dict[str, list[tuple[str | None, int]]] = {}
    for symbol, status, count in rows:
        status_by_symbol.setdefault(symbol, []).append((status, count))

    missing = sorted(set(symbols) - set(status_by_symbol))
    if missing:
        raise ValueError(f"数据集 {STOCK_LIST_DATASET} 缺少目标代码: {', '.join(missing)}")

    for symbol, statuses in status_by_symbol.items():
        total_rows = sum(count for _, count in statuses)
        distinct_statuses = {status for status, _ in statuses}
        if total_rows > 1:
            if len(distinct_statuses) > 1:
                raise ValueError(f"数据集 {STOCK_LIST_DATASET} 中代码 {symbol} 有重复记录且状态冲突")
            raise ValueError(f"数据集 {STOCK_LIST_DATASET} 中代码 {symbol} 有重复记录")
        status = statuses[0][0]
        if status != "L":
            raise ValueError(f"数据集 {STOCK_LIST_DATASET} 中代码 {symbol} 的 list_status 为 {status!r}，要求为 'L'")
    return set(status_by_symbol)


def _daily_metrics(data_root: Path, trading_date: date, symbols: list[str]) -> dict[str, tuple[int | None, float | None]]:
    files = _parquet_files(data_root, DAILY_DATASET, trading_date)
    _require_columns(files, DAILY_DATASET, {"symbol", "volume", "amount"}, trading_date)
    rows = _target_query(
        files,
        symbols,
        """SELECT symbol, SUM(volume), SUM(amount)
           FROM read_parquet(?)
           WHERE symbol IN (SELECT UNNEST(?))
           GROUP BY symbol""",
    )
    return {symbol: (volume, amount) for symbol, volume, amount in rows}


def _minute_counts(data_root: Path, trading_date: date, symbols: list[str]) -> dict[str, int]:
    files = _parquet_files(data_root, MINUTE_DATASET, trading_date)
    _require_columns(files, MINUTE_DATASET, {"symbol"}, trading_date)
    rows = _target_query(
        files,
        symbols,
        """SELECT symbol, COUNT(*)
           FROM read_parquet(?)
           WHERE symbol IN (SELECT UNNEST(?))
           GROUP BY symbol""",
    )
    return {symbol: count for symbol, count in rows}


def _make_report(
    symbols: list[str],
    listed_symbols: set[str],
    trading_date: date,
    daily_symbols: set[str],
    minute_symbols: set[str],
    daily_metrics: dict[str, tuple[int | None, float | None]],
    minute_counts: dict[str, int],
) -> dict:
    return {
        "stock_pool_count": len(symbols),
        "list_status_l_count": len(listed_symbols),
        "date": trading_date.isoformat(),
        "daily_symbol_count": len(daily_symbols),
        "minute_symbol_count": len(minute_symbols),
        "daily_volume": {symbol: daily_metrics.get(symbol, (None, None))[0] for symbol in symbols},
        "daily_amount": {symbol: daily_metrics.get(symbol, (None, None))[1] for symbol in symbols},
        "minute_records": {symbol: minute_counts.get(symbol, 0) for symbol in symbols},
        "missing_daily": sorted(set(symbols) - daily_symbols),
        "missing_minute": sorted(set(symbols) - minute_symbols),
    }


def _print_text(report: dict) -> None:
    print(f"股票池数量：{report['stock_pool_count']}")
    print(f"list_status=L 数量：{report['list_status_l_count']}")
    print(f"共同覆盖日期：{report['date']}")
    print(f"日线代码数：{report['daily_symbol_count']}")
    print(f"分钟代码数：{report['minute_symbol_count']}")
    print("每只股票分钟记录数：")
    for symbol, count in report["minute_records"].items():
        print(f"  {symbol}: {count}")
    daily_volume_total = sum(value or 0 for value in report["daily_volume"].values())
    daily_amount_total = sum(value or 0 for value in report["daily_amount"].values())
    print(f"日线成交量总计：{daily_volume_total}")
    print(f"日线成交额总计：{daily_amount_total:g}")
    print("日线成交量/成交额（每只股票）：")
    for symbol in report["daily_volume"]:
        volume = report["daily_volume"][symbol]
        amount = report["daily_amount"][symbol]
        print(f"  {symbol}: volume={volume}, amount={amount}")
    print(f"缺失代码（日线）：{', '.join(report['missing_daily']) or '无'}")
    print(f"缺失代码（分钟）：{', '.join(report['missing_minute']) or '无'}")


def _parse_iso_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"日期必须采用 YYYY-MM-DD 格式: {value}") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError(f"日期必须采用 YYYY-MM-DD 格式: {value}")
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读检查股票池对应的源 Parquet 数据")
    parser.add_argument("--data-root", required=True, type=Path, help="源数据根目录")
    parser.add_argument("--stock-pool", required=True, type=Path, help="股票池 CSV")
    parser.add_argument("--date", type=_parse_iso_date, help="只检查指定日期，不回退到其他日期")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="输出格式")
    args = parser.parse_args(argv)

    try:
        if not args.data_root.is_dir():
            raise ValueError(f"源数据根目录不存在或不是目录: {args.data_root}")
        symbols = load_stock_pool(args.stock_pool)
        listed_symbols = validate_stock_list(args.data_root, symbols)

        if args.date:
            trading_date = args.date
            daily_symbols = symbols_for_date(args.data_root, DAILY_DATASET, trading_date, symbols)
            minute_symbols = symbols_for_date(args.data_root, MINUTE_DATASET, trading_date, symbols)
        else:
            trading_date, daily_symbols, minute_symbols = find_latest_complete_date(args.data_root, symbols)

        daily_metrics = _daily_metrics(args.data_root, trading_date, symbols)
        minute_counts = _minute_counts(args.data_root, trading_date, symbols)
        report = _make_report(
            symbols,
            listed_symbols,
            trading_date,
            daily_symbols,
            minute_symbols,
            daily_metrics,
            minute_counts,
        )
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            _print_text(report)
        if report["missing_daily"] or report["missing_minute"]:
            print("指定日期未完整覆盖股票池。", file=sys.stderr)
            return 1
        return 0
    except (OSError, ValueError, duckdb.Error) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
