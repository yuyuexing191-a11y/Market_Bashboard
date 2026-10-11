from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine


def database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("未设置 DATABASE_URL")
    return value


def create_database_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)
