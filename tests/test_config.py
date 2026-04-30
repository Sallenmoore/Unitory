from pathlib import Path

import pytest

from app.config import _env_or_file

pytestmark = pytest.mark.unit


def test_returns_default_when_neither_env_nor_file_set(monkeypatch):
    monkeypatch.delenv("UNITORY_TEST_SECRET", raising=False)
    monkeypatch.delenv("UNITORY_TEST_SECRET_FILE", raising=False)
    assert _env_or_file("UNITORY_TEST_SECRET", default="fallback") == "fallback"


def test_returns_env_when_only_env_set(monkeypatch):
    monkeypatch.setenv("UNITORY_TEST_SECRET", "from-env")
    monkeypatch.delenv("UNITORY_TEST_SECRET_FILE", raising=False)
    assert _env_or_file("UNITORY_TEST_SECRET") == "from-env"


def test_reads_file_when_file_set_and_readable(monkeypatch, tmp_path: Path):
    secret_path = tmp_path / "secret"
    secret_path.write_text("from-file\n")
    monkeypatch.setenv("UNITORY_TEST_SECRET_FILE", str(secret_path))
    monkeypatch.setenv("UNITORY_TEST_SECRET", "from-env")
    assert _env_or_file("UNITORY_TEST_SECRET") == "from-file"


def test_falls_back_to_env_when_file_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("UNITORY_TEST_SECRET_FILE", str(tmp_path / "does-not-exist"))
    monkeypatch.setenv("UNITORY_TEST_SECRET", "from-env")
    assert _env_or_file("UNITORY_TEST_SECRET") == "from-env"


def test_falls_back_to_env_when_file_empty(monkeypatch, tmp_path: Path):
    empty = tmp_path / "empty"
    empty.write_text("")
    monkeypatch.setenv("UNITORY_TEST_SECRET_FILE", str(empty))
    monkeypatch.setenv("UNITORY_TEST_SECRET", "from-env")
    assert _env_or_file("UNITORY_TEST_SECRET") == "from-env"


def test_strips_trailing_whitespace_from_file(monkeypatch, tmp_path: Path):
    p = tmp_path / "with-trailing"
    p.write_text("token-value\n\n")
    monkeypatch.setenv("UNITORY_TEST_SECRET_FILE", str(p))
    monkeypatch.delenv("UNITORY_TEST_SECRET", raising=False)
    assert _env_or_file("UNITORY_TEST_SECRET") == "token-value"
