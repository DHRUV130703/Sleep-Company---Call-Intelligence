"""Shared test setup: every test run gets its own empty data folder and database."""

import pytest
from sqlmodel import Session, SQLModel

from app import config, db


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    # Never read the developer's real .env (it holds real API keys): tests use code defaults only.
    monkeypatch.setitem(config.Settings.model_config, "env_file", None)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    for key in ("DATABASE_URL", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(key, "")
    # Tests never call real AI: fake transcriber + fake analyser unless a test opts in.
    monkeypatch.setenv("TRANSCRIBER", "fake")
    monkeypatch.setenv("ANALYZER", "fake")
    from app import providers

    providers.reset_providers()
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    yield tmp_path / "data"
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()


@pytest.fixture
def session(isolated_data_dir):
    import app.models  # noqa: F401  (register tables)

    engine = db.get_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
