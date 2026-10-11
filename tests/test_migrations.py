from pathlib import Path
import os

from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import create_engine, inspect


def test_alembic_contains_market_tables_revision() -> None:
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    revisions = list(ScriptDirectory.from_config(config).walk_revisions())

    assert any(
        "market tables" in (revision.doc or "").lower()
        for revision in revisions
    )


def test_postgresql_migration_exposes_market_tables() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL 未设置")

    inspector = inspect(create_engine(database_url))

    assert set(inspector.get_table_names()).issuperset(
        {"stocks", "daily_quotes", "minute_quotes"}
    )
    assert inspector.get_pk_constraint("daily_quotes")["constrained_columns"] == [
        "symbol",
        "trade_date",
    ]
    assert inspector.get_pk_constraint("minute_quotes")["constrained_columns"] == [
        "symbol",
        "trade_time",
    ]
    assert inspector.get_indexes("daily_quotes") == []
    assert inspector.get_indexes("minute_quotes") == []
