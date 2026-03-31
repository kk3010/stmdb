from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_no_api_keys_in_source_files():
	for p in Path("app").rglob("*.py"):
		text = p.read_text(encoding="utf-8")
		assert "sk-ant" not in text
		assert "pa-" not in text


def test_no_hardcoded_passwords_in_source_files():
	for p in Path("app").rglob("*.py"):
		for line in p.read_text(encoding="utf-8").splitlines():
			assert "password = \"" not in line
			assert "password='" not in line


def test_anthropic_key_hidden_in_repr(settings_override):
	assert "sk-ant-test-key" not in repr(settings_override)


def test_voyage_key_hidden_in_repr(settings_override):
	assert "pa-test-key" not in repr(settings_override)


def test_db_password_hidden_in_repr(settings_override):
	assert "test_password" not in repr(settings_override)


@pytest.mark.asyncio
async def test_chat_complete_error_hides_all_internals(mocker):
	from app.tools import llm

	client = mocker.MagicMock()
	client.messages.create = mocker.AsyncMock(
		side_effect=Exception("anthropic.APIStatusError: 429 Too Many Requests")
	)
	mocker.patch("app.tools.llm.get_llm_client", return_value=client)
	with pytest.raises(RuntimeError) as exc_info:
		await llm.chat_complete("s", [])
	assert "APIStatusError" not in str(exc_info.value)
	assert "429" not in str(exc_info.value)
	assert "anthropic" not in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_execute_query_error_hides_asyncpg_internals(mocker):
	from app.tools import postgres

	mocker.patch(
		"app.tools.postgres.asyncpg.connect",
		mocker.AsyncMock(side_effect=Exception("asyncpg.exceptions.UndefinedTableError: ...")),
	)
	with pytest.raises(RuntimeError) as exc_info:
		await postgres.execute_query("SELECT 1")
	assert "asyncpg" not in str(exc_info.value).lower()
	assert "UndefinedTableError" not in str(exc_info.value)


def test_ruff_check_exits_zero():
	result = subprocess.run(["uv", "run", "ruff", "check", "app/"], check=False)
	assert result.returncode == 0


def test_env_is_gitignored():
	result = subprocess.run(["git", "check-ignore", "-v", ".env"], check=False)
	assert result.returncode == 0
