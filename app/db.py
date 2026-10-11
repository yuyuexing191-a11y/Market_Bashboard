from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL


PROJECT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def database_url() -> str:
    # Read the project file without changing the caller's environment.
    settings = {**dotenv_values(PROJECT_ENV_FILE, interpolate=False), **os.environ}
    value = settings.get("DATABASE_URL")
    if value:
        return value

    required = ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    if all(settings.get(key) for key in required):
        return URL.create(
            "postgresql+psycopg",
            username=settings["POSTGRES_USER"],
            password=settings["POSTGRES_PASSWORD"],
            host="localhost",
            port=int(settings.get("DB_PORT") or "5432"),
            database=settings["POSTGRES_DB"],
        ).render_as_string(hide_password=False)

    raise RuntimeError(
        "未设置 DATABASE_URL：请在项目根目录 .env 中配置 DATABASE_URL，"
        "或完整配置 POSTGRES_USER、POSTGRES_PASSWORD、POSTGRES_DB"
    )


def create_database_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)
