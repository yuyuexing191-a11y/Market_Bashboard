from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import create_database_engine


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_database_engine()
    app.state.engine = engine
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="Market Dashboard API", lifespan=lifespan)


@app.get("/health")
def health(request: Request) -> JSONResponse:
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("数据库健康检查失败")
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "down",
                "detail": "数据库不可用",
            },
        )

    return JSONResponse(
        status_code=200,
        content={"status": "ok", "database": "up"},
    )
