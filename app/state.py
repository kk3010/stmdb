from __future__ import annotations

import logging
from typing import TypedDict

from langchain_core.messages import BaseMessage, HumanMessage

from app.logging_utils import instrument_module_functions


class GraphState(TypedDict):
	messages: list[BaseMessage]
	intent: str | None
	retrieved_col_docs: list[dict]
	enhanced_query: str | None
	confirmation_message: str | None
	confirmation_status: str | None
	sql: str | None
	db_results: list[dict] | None
	final_response: str | None
	error: str | None
	retry_count: int


VALID_INTENTS: frozenset[str] = frozenset({"metadata", "db_query", "out_of_scope"})
MAX_RETRIES: int = 3


def initial_state(user_message: str) -> GraphState:
	return {
		"messages": [HumanMessage(content=user_message)],
		"intent": None,
		"retrieved_col_docs": [],
		"enhanced_query": None,
		"confirmation_message": None,
		"confirmation_status": None,
		"sql": None,
		"db_results": None,
		"final_response": None,
		"error": None,
		"retry_count": 0,
	}


instrument_module_functions(globals(), logging.getLogger("smtdb.state"), exclude={"instrument_module_functions"})
