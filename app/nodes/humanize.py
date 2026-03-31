from __future__ import annotations

import json
import logging

from app.config import settings
from app.logging_utils import instrument_module_functions
from app.prompts import build_humanize_prompt
from app.state import GraphState
from app.tools.llm import chat_complete


async def humanize_response(state: GraphState) -> dict:
	if not state.get("db_results"):
		return {
			"final_response": (
				"No results were found for your query. "
				"This may mean no records match your criteria - "
				"check filter values are case-sensitive (e.g. INACTIVE not Inactive)."
			)
		}

	try:
		response = await chat_complete(
			*build_humanize_prompt(
				state.get("sql") or "",
				state.get("db_results") or [],
				state.get("retrieved_col_docs") or [],
				settings.max_result_rows,
			)
		)
	except RuntimeError as exc:
		return {"error": str(exc)}

	try:
		summary = json.loads(response)["summary"]
	except (json.JSONDecodeError, KeyError):
		summary = response
	return {"final_response": summary}


instrument_module_functions(
	globals(),
	logging.getLogger("smtdb.nodes.humanize"),
	exclude={"instrument_module_functions"},
	include={"humanize_response"},
)

