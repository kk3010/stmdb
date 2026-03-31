from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import asyncpg

from app.config import settings
from app.logging_utils import instrument_module_functions

logger = logging.getLogger("smtdb.postgres")


def _serialize(value: object) -> object:
	if isinstance(value, Decimal):
		return str(value)
	if isinstance(value, datetime):
		return value.isoformat()
	if isinstance(value, date):
		return value.isoformat()
	if isinstance(value, UUID):
		return str(value)
	return value


async def execute_query(sql: str, max_rows: int | None = None) -> list[dict]:
	sql = sql.strip()
	if not sql.lower().startswith("select"):
		raise ValueError("Only SELECT statements are permitted.")

	row_limit = max_rows if max_rows is not None else settings.max_result_rows
	if " limit " not in sql.lower():
		sql = sql.rstrip(";") + f" LIMIT {row_limit}"

	conn = None
	try:
		conn = await asyncpg.connect(settings.db_url)
		rows = await conn.fetch(sql)
		result: list[dict] = []
		for row in rows:
			row_dict = dict(row)
			result.append({k: _serialize(v) for k, v in row_dict.items()})
		return result
	except Exception as exc:  # noqa: BLE001
		logger.error("Database query failed", exc_info=exc)
		raise RuntimeError("The query could not be completed. Please try rephrasing.") from None
	finally:
		if conn is not None:
			await conn.close()


async def get_table_columns(table_name: str) -> list[str]:
	query = """
	SELECT column_name
	FROM information_schema.columns
	WHERE table_schema = 'public' AND table_name = $1
	ORDER BY ordinal_position
	"""
	conn = await asyncpg.connect(settings.db_url)
	try:
		rows = await conn.fetch(query, table_name)
		return [r["column_name"] for r in rows]
	finally:
		await conn.close()


async def validate_schema(table_name: str, doc_column_names: list[str]) -> None:
	try:
		actual = await get_table_columns(table_name)
		expected = set(doc_column_names)
		actual_set = set(actual)
		missing_in_db = sorted(expected - actual_set)
		missing_in_docs = sorted(actual_set - expected)
		if missing_in_db:
			logger.warning("Columns missing in DB: %s", missing_in_db)
		if missing_in_docs:
			logger.warning("Columns missing in docs: %s", missing_in_docs)
	except Exception as exc:  # noqa: BLE001
		logger.warning("Schema validation skipped due to DB issue", exc_info=exc)


instrument_module_functions(
	globals(),
	logger,
	exclude={"instrument_module_functions"},
	include={"execute_query"},
)
