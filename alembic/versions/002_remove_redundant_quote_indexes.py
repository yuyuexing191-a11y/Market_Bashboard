"""remove redundant quote indexes

Revision ID: 002_drop_quote_indexes
Revises: 001_create_market_tables
"""

from alembic import op


revision = "002_drop_quote_indexes"
down_revision = "001_create_market_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_daily_quotes_symbol_trade_date", table_name="daily_quotes")
    op.drop_index("ix_minute_quotes_symbol_trade_time", table_name="minute_quotes")


def downgrade() -> None:
    op.create_index(
        "ix_daily_quotes_symbol_trade_date", "daily_quotes", ["symbol", "trade_date"]
    )
    op.create_index(
        "ix_minute_quotes_symbol_trade_time", "minute_quotes", ["symbol", "trade_time"]
    )
