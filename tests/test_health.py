from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app import main


def test_health_returns_service_and_database_up(monkeypatch):
    calls: list[str] = []

    class Connection:
        def execute(self, statement):
            calls.append(str(statement))

    class Engine:
        def connect(self):
            class Context:
                def __enter__(self):
                    return Connection()

                def __exit__(self, exc_type, exc, traceback):
                    return False

            return Context()

        def dispose(self):
            pass

    monkeypatch.setattr(main, "create_database_engine", lambda: Engine())

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}
    assert calls == ["SELECT 1"]


def test_health_returns_degraded_without_exposing_database_error(monkeypatch, caplog):
    class Engine:
        def connect(self):
            raise RuntimeError("postgresql://user:secret@example.invalid/db")

        def dispose(self):
            pass

    monkeypatch.setattr(main, "create_database_engine", lambda: Engine())

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "database": "down",
        "detail": "数据库不可用",
    }
    assert "postgresql://user:secret@example.invalid/db" in caplog.text


def test_application_startup_reports_missing_database_configuration(monkeypatch):
    def missing_configuration():
        raise RuntimeError("未设置 DATABASE_URL")

    monkeypatch.setattr(main, "create_database_engine", missing_configuration)

    with pytest.raises(RuntimeError, match="未设置 DATABASE_URL"):
        with TestClient(main.app):
            pass
