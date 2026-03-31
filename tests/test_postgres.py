from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest


@pytest.mark.asyncio
async def test_execute_query_rejects_delete():
	from app.tools.postgres import execute_query

	with pytest.raises(ValueError):
		await execute_query("DELETE FROM cost_centers")


@pytest.mark.asyncio
async def test_execute_query_rejects_drop():
	from app.tools.postgres import execute_query

	with pytest.raises(ValueError):
		await execute_query("DROP TABLE cost_centers")


@pytest.mark.asyncio
async def test_execute_query_rejects_insert():
	from app.tools.postgres import execute_query

	with pytest.raises(ValueError):
		await execute_query("INSERT INTO cost_centers VALUES (1)")


@pytest.mark.asyncio
async def test_execute_query_rejects_update():
	from app.tools.postgres import execute_query

	with pytest.raises(ValueError):
		await execute_query("UPDATE cost_centers SET status='ACTIVE'")


@pytest.mark.asyncio
async def test_execute_query_adds_limit_when_absent(mocker):
	from app.tools import postgres

	conn = mocker.AsyncMock()
	conn.fetch = mocker.AsyncMock(return_value=[])
	mocker.patch("app.tools.postgres.asyncpg.connect", mocker.AsyncMock(return_value=conn))
	await postgres.execute_query("SELECT 1", max_rows=7)
	assert "LIMIT 7" in conn.fetch.call_args.args[0]


@pytest.mark.asyncio
async def test_execute_query_does_not_double_add_limit(mocker):
	from app.tools import postgres

	conn = mocker.AsyncMock()
	conn.fetch = mocker.AsyncMock(return_value=[])
	mocker.patch("app.tools.postgres.asyncpg.connect", mocker.AsyncMock(return_value=conn))
	await postgres.execute_query("SELECT 1 LIMIT 5")
	assert conn.fetch.call_args.args[0].lower().count("limit") == 1


@pytest.mark.asyncio
async def test_execute_query_returns_list_of_dicts(mocker):
	from app.tools import postgres

	conn = mocker.AsyncMock()
	conn.fetch = mocker.AsyncMock(return_value=[{"a": 1}])
	mocker.patch("app.tools.postgres.asyncpg.connect", mocker.AsyncMock(return_value=conn))
	out = await postgres.execute_query("SELECT 1")
	assert isinstance(out, list)
	assert isinstance(out[0], dict)


@pytest.mark.asyncio
async def test_execute_query_serialises_decimal(mocker):
	from app.tools import postgres

	conn = mocker.AsyncMock()
	conn.fetch = mocker.AsyncMock(return_value=[{"v": Decimal("1234.56")}])
	mocker.patch("app.tools.postgres.asyncpg.connect", mocker.AsyncMock(return_value=conn))
	out = await postgres.execute_query("SELECT 1")
	assert out[0]["v"] == "1234.56"


@pytest.mark.asyncio
async def test_execute_query_serialises_date(mocker):
	from app.tools import postgres

	conn = mocker.AsyncMock()
	conn.fetch = mocker.AsyncMock(return_value=[{"v": date(2024, 3, 15)}])
	mocker.patch("app.tools.postgres.asyncpg.connect", mocker.AsyncMock(return_value=conn))
	out = await postgres.execute_query("SELECT 1")
	assert out[0]["v"] == "2024-03-15"


@pytest.mark.asyncio
async def test_execute_query_friendly_error_hides_asyncpg(mocker):
	from app.tools import postgres

	mocker.patch("app.tools.postgres.asyncpg.connect", mocker.AsyncMock(side_effect=Exception("asyncpg boom")))
	with pytest.raises(RuntimeError) as exc_info:
		await postgres.execute_query("SELECT 1")
	assert "asyncpg" not in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_validate_schema_logs_warning_for_missing_column(mocker, caplog):
	from app.tools import postgres

	mocker.patch("app.tools.postgres.get_table_columns", mocker.AsyncMock(return_value=["cc_code"]))
	await postgres.validate_schema("cost_centers", ["cc_code", "status"])
	assert "missing" in caplog.text.lower()


@pytest.mark.asyncio
async def test_validate_schema_does_not_raise_on_connection_error(mocker):
	from app.tools import postgres

	mocker.patch("app.tools.postgres.get_table_columns", mocker.AsyncMock(side_effect=Exception("boom")))
	await postgres.validate_schema("cost_centers", ["cc_code"])


@pytest.mark.asyncio
@pytest.mark.skipif(True, reason="RUN_INTEGRATION=1 only")
async def test_real_select_from_cost_centers():
	from app.tools.postgres import execute_query

	result = await execute_query("SELECT cc_code FROM cost_centers LIMIT 1")
	assert result[0]["cc_code"].startswith("KS-")
