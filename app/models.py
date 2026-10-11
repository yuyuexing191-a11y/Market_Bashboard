from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    TIMESTAMP,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stocks"

    symbol: Mapped[str] = mapped_column(String(12), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sector: Mapped[str] = mapped_column(String(30), nullable=False)
    source_industry: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)
    list_status: Mapped[str] = mapped_column(String(2), nullable=False)


class DailyQuote(Base):
    __tablename__ = "daily_quotes"
    __table_args__ = (
        CheckConstraint("open > 0 AND high > 0 AND low > 0 AND close > 0", name="ck_daily_positive_prices"),
        CheckConstraint("high >= low", name="ck_daily_high_gte_low"),
        CheckConstraint("volume >= 0", name="ck_daily_nonnegative_volume"),
        CheckConstraint("amount >= 0", name="ck_daily_nonnegative_amount"),
    )

    symbol: Mapped[str] = mapped_column(ForeignKey("stocks.symbol"), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)


class MinuteQuote(Base):
    __tablename__ = "minute_quotes"
    __table_args__ = (
        CheckConstraint("open > 0 AND high > 0 AND low > 0 AND close > 0", name="ck_minute_positive_prices"),
        CheckConstraint("high >= low", name="ck_minute_high_gte_low"),
        CheckConstraint("volume >= 0", name="ck_minute_nonnegative_volume"),
        CheckConstraint("amount >= 0", name="ck_minute_nonnegative_amount"),
    )

    symbol: Mapped[str] = mapped_column(ForeignKey("stocks.symbol"), primary_key=True)
    trade_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=False), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
