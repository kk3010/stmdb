from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import dotenv_values


REQUIRED_FILES = [
	"app/__init__.py",
	"app/config.py",
	"app/state.py",
	"app/prompts.py",
	"app/graph.py",
	"app/nodes/__init__.py",
	"app/nodes/classify.py",
	"app/nodes/retrieve.py",
	"app/nodes/map_columns.py",
	"app/nodes/enhance.py",
	"app/nodes/confirm.py",
	"app/nodes/sql.py",
	"app/nodes/humanize.py",
	"app/tools/__init__.py",
	"app/tools/llm.py",
	"app/tools/chroma.py",
	"app/tools/postgres.py",
	"db/seed.sql",
	"docs/columns.json",
	"scripts/check_apis.py",
	"tests/conftest.py",
	"tests/test_phase0_skeleton.py",
	"tests/test_config.py",
	"tests/test_state.py",
	"tests/test_llm.py",
	"tests/test_postgres.py",
	"tests/test_chroma.py",
	"tests/test_prompts.py",
	"tests/test_nodes.py",
	"tests/test_graph.py",
	"tests/test_streamlit_app.py",
	"tests/test_hardening.py",
	"tests/integration/test_e2e.py",
	"streamlit_app.py",
	"Makefile",
	".env.example",
]


def test_all_required_files_exist():
	for path in REQUIRED_FILES:
		assert os.path.exists(path), path


def test_env_example_has_all_required_keys():
	values = dotenv_values(".env.example")
	required = {
		"ANTHROPIC_API_KEY",
		"CLAUDE_MODEL",
		"CLAUDE_MAX_TOKENS",
		"VOYAGE_API_KEY",
		"VOYAGE_MODEL",
		"DB_HOST",
		"DB_PORT",
		"DB_NAME",
		"DB_USER",
		"DB_PASSWORD",
		"TABLE_NAME",
		"CHROMA_PATH",
		"COLUMN_DOCS_PATH",
		"SIMILARITY_THRESHOLD",
		"MAX_RESULT_ROWS",
		"LOG_PATH",
	}
	assert required.issubset(values.keys())


def test_gitignore_excludes_env_and_secrets():
	lines = Path(".gitignore").read_text(encoding="utf-8").splitlines()
	assert ".env" in lines
	assert "chroma_db/" in lines
	assert "logs/" in lines


def test_pyproject_has_pytest_and_ruff_config():
	import tomllib

	doc = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
	assert "pytest" in doc["tool"]
	assert "ruff" in doc["tool"]


def test_conftest_fixtures_are_callable():
	import tests.conftest as conftest

	assert callable(conftest.settings_override)
	assert callable(conftest.sample_columns)
	assert callable(conftest.mock_anthropic_client)
	assert callable(conftest.mock_voyage_client)
	assert callable(conftest.mock_chroma_collection)


def test_columns_json_has_24_entries():
	data = json.loads(Path("docs/columns.json").read_text(encoding="utf-8"))
	assert len(data["columns"]) == 24


def test_columns_json_every_entry_has_required_fields():
	data = json.loads(Path("docs/columns.json").read_text(encoding="utf-8"))
	for col in data["columns"]:
		for field in ["column_name", "human_label", "data_type", "nullable", "description", "example_values"]:
			assert field in col


def test_seed_sql_has_create_table_and_inserts():
	content = Path("db/seed.sql").read_text(encoding="utf-8")
	assert "CREATE TABLE cost_centers" in content
	assert content.count("KS-") >= 100
