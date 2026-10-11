"""create market tables

Revision ID: 001_create_market_tables
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "001_create_market_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stocks",
        sa.Column("symbol", sa.String(length=12), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sector", sa.String(length=30), nullable=False),
        sa.Column("source_industry", sa.String(length=100), nullable=False),
        sa.Column("exchange", sa.String(length=10), nullable=False),
        sa.Column("list_status", sa.String(length=2), nullable=False),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_table(
        "daily_quotes",
        sa.Column("symbol", sa.String(length=12), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0",
            name="ck_daily_positive_prices",
        ),
        sa.CheckConstraint("high >= low", name="ck_daily_high_gte_low"),
        sa.CheckConstraint("volume >= 0", name="ck_daily_nonnegative_volume"),
        sa.CheckConstraint("amount >= 0", name="ck_daily_nonnegative_amount"),
        sa.ForeignKeyConstraint(["symbol"], ["stocks.symbol"]),
        sa.PrimaryKeyConstraint("symbol", "trade_date"),
    )
    op.create_index(
        "ix_daily_quotes_symbol_trade_date",
        "daily_quotes",
        ["symbol", "trade_date"],
    )
    op.create_table(
        "minute_quotes",
        sa.Column("symbol", sa.String(length=12), nullable=False),
        sa.Column("trade_time", sa.TIMESTAMP(timezone=False), nullable=False),
        sa.Column("open", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=False),
        sa.CheckConstraint(
            "open > 0 AND high > 0 AND low > 0 AND close > 0",
            name="ck_minute_positive_prices",
        ),
        sa.CheckConstraint("high >= low", name="ck_minute_high_gte_low"),
        sa.CheckConstraint("volume >= 0", name="ck_minute_nonnegative_volume"),
        sa.CheckConstraint("amount >= 0", name="ck_minute_nonnegative_amount"),
        sa.ForeignKeyConstraint(["symbol"], ["stocks.symbol"]),
        sa.PrimaryKeyConstraint("symbol", "trade_time"),
    )
    op.create_index(
        "ix_minute_quotes_symbol_trade_time",
        "minute_quotes",
        ["symbol", "trade_time"],
    )


def downgrade() -> None:
    op.drop_table("minute_quotes")
    op.drop_table("daily_quotes")
    op.drop_table("stocks")
