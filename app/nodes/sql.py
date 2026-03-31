from __future__ import annotations

import logging

import sqlglot

from app.config import settings
from app.logging_utils import instrument_module_functions
from app.prompts import build_sql_prompt
from app.state import GraphState
from app.tools.llm import chat_complete
from app.tools.postgres import execute_query

logger = logging.getLogger("smtdb.nodes.sql")


async def build_and_run_sql(state: GraphState) -> dict:
	try:
		response = await chat_complete(
			*build_sql_prompt(state["enhanced_query"] or "", settings.table_name, state["retrieved_col_docs"])
		)
	except RuntimeError as exc:
		return {"error": str(exc)}

	sql = response.strip()
	for fence in ["```sql", "```SQL", "```"]:
		if sql.startswith(fence):
			sql = sql[len(fence) :]
	sql = sql.rstrip("`").strip()

	try:
		parsed = sqlglot.parse_one(sql, dialect="postgres")
	except sqlglot.errors.ParseError:
		logger.debug("Invalid SQL generated: %s", sql)
		return {"error": "The generated query was not valid. Please try rephrasing."}

	if not isinstance(parsed, sqlglot.expressions.Select):
		return {"error": "Only SELECT queries are supported."}

	try:
		results = await execute_query(sql)
	except (ValueError, RuntimeError) as exc:
		return {"error": str(exc)}

	return {"sql": sql, "db_results": results}


instrument_module_functions(
	globals(),
	logger,
	exclude={"instrument_module_functions"},
	include={"build_and_run_sql"},
)

