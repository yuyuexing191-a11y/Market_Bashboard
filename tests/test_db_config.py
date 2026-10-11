from sqlalchemy.engine import make_url

import pytest

from app import db


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / '.env'
    monkeypatch.setattr(db, 'PROJECT_ENV_FILE', path, raising=False)
    for key in ['DATABASE_URL', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB', 'DB_PORT']:
        monkeypatch.delenv(key, raising=False)
    return path


def test_reads_database_url_from_project_env_even_in_another_directory(env_file, tmp_path, monkeypatch):
    url = 'postgresql+psycopg://student:secret@localhost:5432/course'
    env_file.write_text(f'DATABASE_URL={url}\n', encoding='utf-8')
    other = tmp_path / 'other'
    other.mkdir()
    monkeypatch.chdir(other)

    assert db.database_url() == url


def test_explicit_environment_url_overrides_project_env(env_file, monkeypatch):
    env_file.write_text('DATABASE_URL=postgresql+psycopg://file:secret@localhost/file\n')
    url = 'postgresql+psycopg://shell:secret@localhost/shell'
    monkeypatch.setenv('DATABASE_URL', url)

    assert db.database_url() == url


def test_builds_url_from_existing_compose_settings_and_preserves_special_password(env_file):
    env_file.write_text(
        "POSTGRES_USER=student\nPOSTGRES_PASSWORD='p@ss:/%$word'\n"
        'POSTGRES_DB=course\nDB_PORT=55432\n', encoding='utf-8'
    )

    url = make_url(db.database_url())

    assert url.username == 'student'
    assert url.password == 'p@ss:/%$word'
    assert url.database == 'course'
    assert url.host == 'localhost'
    assert url.port == 55432


def test_missing_configuration_has_clear_error(env_file):
    with pytest.raises(RuntimeError, match='DATABASE_URL'):
        db.database_url()


def test_incomplete_compose_settings_do_not_guess_credentials(env_file):
    env_file.write_text('POSTGRES_USER=student\nPOSTGRES_DB=course\n')

    with pytest.raises(RuntimeError, match='DATABASE_URL'):
        db.database_url()
