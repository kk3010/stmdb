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


def _render_message_body(message: dict[str, Any]) -> None:
	st.markdown(message["content"])
	if "dataframe" in message:
		st.dataframe(message["dataframe"], use_container_width=True)


def _append_assistant_message(content: str, dataframe: pd.DataFrame | None = None) -> dict[str, Any]:
	message: dict[str, Any] = {"role": "assistant", "content": content}
	if dataframe is not None:
		message["dataframe"] = dataframe
	st.session_state.messages.append(message)
	return message


def _build_dataframe(db_results: list[dict], col_docs: list[dict]) -> pd.DataFrame:
	label_map = {c.get("column_name"): c.get("human_label") for c in col_docs}
	df = pd.DataFrame(db_results)
	df.rename(columns=lambda c: label_map.get(c, c), inplace=True)
	return df


def _extract_interrupt_message(payload: Any) -> str:
	# Direct dict with message key (legacy path)
	if isinstance(payload, dict) and "message" in payload and payload["message"]:
		return str(payload["message"])

	# Result dict with __interrupt__ key
	if isinstance(payload, dict) and "__interrupt__" in payload:
		interrupts = payload["__interrupt__"]
		if interrupts:
			value = getattr(interrupts[0], "value", None)
			if isinstance(value, dict) and value.get("message"):
				return str(value["message"])

	# GraphInterrupt exception: exc.args is a tuple of Interrupt objects
	if hasattr(payload, "args") and payload.args:
		for item in payload.args:
			value = getattr(item, "value", None)
			if isinstance(value, dict) and value.get("message"):
				return str(value["message"])
			if isinstance(item, dict) and item.get("message"):
				return str(item["message"])

	return "Please confirm the query interpretation."


def _handle_interrupt(exc: Exception) -> dict[str, Any]:
	confirmation = _extract_interrupt_message(exc)
	st.session_state.awaiting_confirmation = True
	return _append_assistant_message(confirmation + "\n\nReply yes/no/rephrase")


def _is_interrupt_payload(payload: Any) -> bool:
	# Result dict
	if isinstance(payload, dict) and "__interrupt__" in payload:
		return True
	if isinstance(payload, dict) and "message" in payload:
		return True
	# GraphInterrupt exception: args is a tuple of Interrupt objects
	if hasattr(payload, "args") and getattr(payload, "args", None):
		for item in payload.args:
			if hasattr(item, "value"):  # Interrupt namedtuple/object
				return True
			if isinstance(item, dict) and ("__interrupt__" in item or "message" in item):
				return True
	return False


def _handle_interrupt_result(result: dict) -> dict[str, Any] | None:
	if "__interrupt__" not in result:
		return None
	confirmation = _extract_interrupt_message(result)
	st.session_state.awaiting_confirmation = True
	return _append_assistant_message(confirmation + "\n\nReply yes/no/rephrase")



def _handle_result(result: dict) -> tuple[bool, dict[str, Any] | None]:
	interrupt_message = _handle_interrupt_result(result)
	if interrupt_message is not None:
		return True, interrupt_message

	if result.get("error"):
		logger.error("Graph error: %s", result.get("error"))
		return False, _append_assistant_message("Something went wrong. Please try rephrasing.")

	final_response = result.get("final_response")
	if final_response:
		dataframe = None
		if result.get("db_results"):
			dataframe = _build_dataframe(result["db_results"], result.get("retrieved_col_docs", []))
		return False, _append_assistant_message(final_response, dataframe)
	return False, None


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
			_render_message_body(msg)

	user_input = st.chat_input("Ask about cost centers...")
	if not user_input:
		return

	config = {"configurable": {"thread_id": st.session_state.thread_id}}
	st.session_state.messages.append({"role": "user", "content": user_input})
	with st.chat_message("user"):
		st.markdown(user_input)

	try:
		with st.chat_message("assistant"):
			with st.spinner("Thinking..."):
				if st.session_state.awaiting_confirmation:
					result = asyncio.run(_get_graph().ainvoke(Command(resume=user_input), config=config))
				else:
					result = asyncio.run(_get_graph().ainvoke(initial_state(user_input), config=config))
			still_waiting, assistant_message = _handle_result(result)
			st.session_state.awaiting_confirmation = still_waiting
			if assistant_message is not None:
				_render_message_body(assistant_message)
	except Exception as exc:  # noqa: BLE001
		if _is_interrupt_payload(exc):
			with st.chat_message("assistant"):
				_render_message_body(_handle_interrupt(exc))
		else:
			logger.error("Unhandled app error", exc_info=exc)
			with st.chat_message("assistant"):
				_render_message_body(_append_assistant_message("Something went wrong. Please try rephrasing."))


if __name__ == "__main__":
	main()


instrument_module_functions(globals(), logger, exclude={"instrument_module_functions"})
