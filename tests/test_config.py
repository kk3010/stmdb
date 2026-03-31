from __future__ import annotations

import importlib

import pytest


def test_settings_loads_all_fields(settings_override):
	assert settings_override.db_name == "smtdb_test"
	assert settings_override.table_name == "cost_centers"


def test_db_url_property(settings_override):
	assert settings_override.db_url == "postgresql://test_user:test_password@localhost:5432/smtdb_test"


def test_missing_db_name_raises(monkeypatch):
	monkeypatch.delenv("DB_NAME", raising=False)
	from pydantic import ValidationError
	from app.config import Settings

	with pytest.raises(ValidationError):
		Settings(_env_file=None)


def test_missing_anthropic_key_raises(monkeypatch):
	monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
	from pydantic import ValidationError
	from app.config import Settings

	with pytest.raises(ValidationError):
		Settings(_env_file=None)


def test_similarity_threshold_default(monkeypatch):
	monkeypatch.delenv("SIMILARITY_THRESHOLD", raising=False)
	from app.config import Settings

	assert Settings().similarity_threshold == 0.75


def test_anthropic_key_hidden_in_repr(settings_override):
	assert "sk-ant-test-key" not in repr(settings_override)


def test_voyage_key_hidden_in_repr(settings_override):
	assert "pa-test-key" not in repr(settings_override)


def test_db_password_hidden_in_repr(settings_override):
	assert "test_password" not in repr(settings_override)


def test_setup_logging_creates_log_directory(tmp_path, monkeypatch):
	monkeypatch.setenv("LOG_PATH", str(tmp_path / "logs" / "chat.log"))
	import app.config as config

	importlib.reload(config)
	logger = config.setup_logging()
	assert (tmp_path / "logs").exists()
	assert logger is not None


def test_setup_logging_returns_smtdb_logger(tmp_path, monkeypatch):
	monkeypatch.setenv("LOG_PATH", str(tmp_path / "logs" / "chat.log"))
	import app.config as config

	importlib.reload(config)
	logger = config.setup_logging()
	assert logger.name == "smtdb"
