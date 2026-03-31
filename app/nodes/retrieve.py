from __future__ import annotations

import logging

from app.prompts import build_docs_prompt
from app.state import GraphState
from app.tools.chroma import search_columns
from app.logging_utils import instrument_module_functions
from app.tools.llm import chat_complete


async def retrieve_docs(state: GraphState) -> dict:
	try:
		docs = await search_columns(str(state["messages"][-1].content))
		return {"retrieved_col_docs": docs}
	except RuntimeError:
		return {"error": "Could not search column documentation. Run 'make ingest' first."}


async def answer_from_docs(state: GraphState) -> dict:
	last_message = str(state["messages"][-1].content)
	system, messages = build_docs_prompt(last_message, state["retrieved_col_docs"])
	try:
		response = await chat_complete(system, messages)
		return {"final_response": response}
	except RuntimeError:
		return {"error": "Could not answer from documentation. Please try again."}


instrument_module_functions(
	globals(),
	logging.getLogger("smtdb.nodes.retrieve"),
	exclude={"instrument_module_functions"},
	include={"retrieve_docs", "answer_from_docs"},
)

