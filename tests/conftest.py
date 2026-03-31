from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def settings_override(monkeypatch):
	values = {
		"ANTHROPIC_API_KEY": "sk-ant-test-key",
		"CLAUDE_MODEL": "claude-sonnet-4-6",
		"CLAUDE_MAX_TOKENS": "1024",
		"VOYAGE_API_KEY": "pa-test-key",
		"VOYAGE_MODEL": "voyage-3.5",
		"DB_HOST": "localhost",
		"DB_PORT": "5432",
		"DB_NAME": "smtdb_test",
		"DB_USER": "test_user",
		"DB_PASSWORD": "test_password",
		"TABLE_NAME": "cost_centers",
		"SIMILARITY_THRESHOLD": "0.5",
		"MAX_RESULT_ROWS": "10",
	}
	for key, value in values.items():
		monkeypatch.setenv(key, value)

	from app.config import Settings

	return Settings()


@pytest.fixture
def sample_columns() -> list[dict]:
	return [
		{
			"column_name": "cc_code",
			"human_label": "Cost Center Code",
			"data_type": "VARCHAR",
			"nullable": False,
			"allowed_values": None,
			"description": "SAP-style cost center code.",
			"example_values": ["KS-FIN-0001"],
		},
		{
			"column_name": "status",
			"human_label": "Status",
			"data_type": "VARCHAR",
			"nullable": False,
			"allowed_values": ["ACTIVE", "INACTIVE", "BLOCKED"],
			"description": "Operational status.",
			"example_values": ["ACTIVE"],
		},
		{
			"column_name": "org_unit_code",
			"human_label": "Organisational Unit Code",
			"data_type": "VARCHAR",
			"nullable": False,
			"allowed_values": ["FIN", "IT", "HR", "OPS", "MKT", "LOG", "R&D", "PRO", "SAL", "ADM"],
			"description": "Department code.",
			"example_values": ["FIN"],
		},
		{
			"column_name": "responsible_person",
			"human_label": "Responsible Person",
			"data_type": "VARCHAR",
			"nullable": False,
			"allowed_values": None,
			"description": "Owner name.",
			"example_values": ["Anna Schmidt"],
		},
		{
			"column_name": "budget_eur",
			"human_label": "Budget (EUR)",
			"data_type": "NUMERIC",
			"nullable": False,
			"allowed_values": None,
			"description": "Annual budget.",
			"example_values": ["100000.00"],
		},
	]


@pytest.fixture
def mock_anthropic_client() -> MagicMock:
	message = SimpleNamespace(
		content=[SimpleNamespace(text='{"intent":"db_query","confidence":0.9,"reason":"test"}')],
		model="claude-sonnet-4-6",
		usage=SimpleNamespace(input_tokens=10, output_tokens=20),
	)
	client = MagicMock()
	client.messages.create = AsyncMock(return_value=message)
	return client


@pytest.fixture
def mock_voyage_client() -> MagicMock:
	result = SimpleNamespace(embeddings=[[0.1] * 1024])
	client = MagicMock()
	client.embed = AsyncMock(return_value=result)
	return client


@pytest.fixture
def mock_chroma_collection() -> MagicMock:
	collection = MagicMock()
	collection.count.return_value = 5
	collection.query.return_value = {
		"ids": [["cc_code", "status", "org_unit_code", "responsible_person", "budget_eur"]],
		"documents": [[
			"Cost Center Code: SAP-style code...",
			"Status: Operational status...",
			"Org Unit Code: Department code...",
			"Responsible Person: Full name...",
			"Budget EUR: Annual budget...",
		]],
		"distances": [[0.05, 0.10, 0.20, 0.35, 0.50]],
		"metadatas": [[
			{"column_name": "cc_code", "human_label": "Cost Center Code", "data_type": "VARCHAR", "nullable": "False", "allowed_values": "null"},
			{"column_name": "status", "human_label": "Status", "data_type": "VARCHAR", "nullable": "False", "allowed_values": '["ACTIVE","INACTIVE","BLOCKED"]'},
			{"column_name": "org_unit_code", "human_label": "Organisational Unit Code", "data_type": "VARCHAR", "nullable": "False", "allowed_values": '["FIN","IT","HR"]'},
			{"column_name": "responsible_person", "human_label": "Responsible Person", "data_type": "VARCHAR", "nullable": "False", "allowed_values": "null"},
			{"column_name": "budget_eur", "human_label": "Budget (EUR)", "data_type": "NUMERIC", "nullable": "False", "allowed_values": "null"},
		]],
	}
	return collection
