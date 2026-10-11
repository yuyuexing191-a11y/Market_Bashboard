from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.data_provider import AkShareProvider
from app.db import create_database_engine
from app.import_service import load_stock_pool, run_daily_import, run_minute_import


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POOL = PROJECT_ROOT / "config" / "stock_pool.csv"


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期必须为 YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导入固定 20 只 A 股行情")
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    subparsers = parser.add_subparsers(dest="command", required=True)

    daily = subparsers.add_parser("daily", help="导入日线行情")
    daily.add_argument("--start-date", required=True, type=_date)
    daily.add_argument("--end-date", required=True, type=_date)

    minute = subparsers.add_parser("minute", help="导入最近窗口的 1 分钟行情")
    minute.add_argument("--lookback-days", type=int, default=5)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "daily" and args.start_date > args.end_date:
        raise SystemExit("--start-date 不能晚于 --end-date")
    if args.command == "minute" and args.lookback_days <= 0:
        raise SystemExit("--lookback-days 必须大于 0")
    try:
        engine = create_database_engine()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    pool = load_stock_pool(args.pool)
    provider = AkShareProvider()
    session_factory = sessionmaker(engine)

    if args.command == "daily":
        report = run_daily_import(
            session_factory, provider, pool, args.start_date, args.end_date
        )
        print(
            f"日线导入完成：股票数={report.stock_count}，新增行数={report.inserted_count}，"
            f"日期范围={report.start}~{report.end}"
        )
        return

    end_datetime = datetime.now().replace(microsecond=0)
    start_datetime = end_datetime - timedelta(days=args.lookback_days)
    report = run_minute_import(
        session_factory, provider, pool, start_datetime, end_datetime
    )
    print(
        f"分钟线导入完成：股票数={report.stock_count}，新增行数={report.inserted_count}，"
        f"日期范围={report.start}~{report.end}，共同交易日={report.common_minute_date}"
    )


if __name__ == "__main__":
    main()
