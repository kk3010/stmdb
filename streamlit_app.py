from __future__ import annotations

import logging
import asyncio
import uuid
from typing import Any

import pandas as pd
import streamlit as st
from langgraph.types import Command

from app.config import setup_logging
from app.graph import build_graph
from app.logging_utils import instrument_module_functions
from app.state import initial_state

setup_logging()
logger = logging.getLogger("smtdb.ui")


@st.cache_resource
def _get_graph():
	"""Cache the graph (and its InMemorySaver) for the lifetime of the server process."""
	return build_graph()


def _build_dataframe(db_results: list[dict], col_docs: list[dict]) -> pd.DataFrame:
	label_map = {c.get("column_name"): c.get("human_label") for c in col_docs}
	df = pd.DataFrame(db_results)
	df.rename(columns=lambda c: label_map.get(c, c), inplace=True)
	return df


def _extract_interrupt_message(payload: Any) -> str:
	if isinstance(payload, dict) and "message" in payload and payload["message"]:
		return str(payload["message"])

	interrupts = None
	if isinstance(payload, dict) and "__interrupt__" in payload:
		interrupts = payload.get("__interrupt__")
	elif hasattr(payload, "args") and payload.args:
		maybe = payload.args[0]
		if isinstance(maybe, dict) and "__interrupt__" in maybe:
			interrupts = maybe.get("__interrupt__")
		elif isinstance(maybe, dict) and "message" in maybe:
			return str(maybe["message"])

	if interrupts:
		first = interrupts[0]
		value = getattr(first, "value", None)
		if isinstance(value, dict) and value.get("message"):
			return str(value["message"])

	return "Please confirm the query interpretation."


def _handle_interrupt(exc: Exception) -> None:
	data = getattr(exc, "args", [{}])[0]
	confirmation = _extract_interrupt_message(data)

	st.session_state.messages.append(
		{"role": "assistant", "content": confirmation + "\n\nReply yes/no/rephrase"}
	)
	st.session_state.awaiting_confirmation = True


def _is_interrupt_payload(payload: Any) -> bool:
	if isinstance(payload, dict) and "__interrupt__" in payload:
		return True
	if isinstance(payload, dict) and "message" in payload:
		return True
	if hasattr(payload, "args") and getattr(payload, "args", None):
		first = payload.args[0]
		return isinstance(first, dict) and ("__interrupt__" in first or "message" in first)
	return False


def _handle_interrupt_result(result: dict) -> bool:
	if "__interrupt__" not in result:
		return False
	confirmation = _extract_interrupt_message(result)
	st.session_state.messages.append(
		{"role": "assistant", "content": confirmation + "\n\nReply yes/no/rephrase"}
	)
	st.session_state.awaiting_confirmation = True
	return True



def _handle_result(result: dict) -> bool:
	if _handle_interrupt_result(result):
		return True

	if result.get("error"):
		logger.error("Graph error: %s", result.get("error"))
		st.error("Something went wrong. Please try rephrasing.")
		return False

	final_response = result.get("final_response")
	if final_response:
		msg: dict = {"role": "assistant", "content": final_response}
		if result.get("db_results"):
			msg["dataframe"] = _build_dataframe(result["db_results"], result.get("retrieved_col_docs", []))
		st.session_state.messages.append(msg)
	return False


def main() -> None:
	if "thread_id" not in st.session_state:
		st.session_state.thread_id = str(uuid.uuid4())
	if "messages" not in st.session_state:
		st.session_state.messages = []
	if "awaiting_confirmation" not in st.session_state:
		st.session_state.awaiting_confirmation = False

	st.title("Cost Center Chat")
	st.caption("Ask plain-English questions about cost center data.")

	for msg in st.session_state.messages:
		with st.chat_message(msg["role"]):
			st.markdown(msg["content"])
			if "dataframe" in msg:
				st.dataframe(msg["dataframe"], use_container_width=True)

	user_input = st.chat_input("Ask about cost centers...")
	if not user_input:
		return

	config = {"configurable": {"thread_id": st.session_state.thread_id}}
	st.session_state.messages.append({"role": "user", "content": user_input})

	try:
		if st.session_state.awaiting_confirmation:
			result = asyncio.run(_get_graph().ainvoke(Command(resume=user_input), config=config))
			still_waiting = _handle_result(result)
			st.session_state.awaiting_confirmation = still_waiting
		else:
			result = asyncio.run(_get_graph().ainvoke(initial_state(user_input), config=config))
			_handle_result(result)
	except Exception as exc:  # noqa: BLE001
		if _is_interrupt_payload(exc):
			_handle_interrupt(exc)
			st.rerun()
		else:
			logger.error("Unhandled app error", exc_info=exc)
			st.error("Something went wrong. Please try rephrasing.")


if __name__ == "__main__":
	main()


instrument_module_functions(globals(), logger, exclude={"instrument_module_functions"})
