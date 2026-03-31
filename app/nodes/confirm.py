from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from app.logging_utils import instrument_module_functions
from app.state import GraphState

CONFIRMED_PHRASES = {
	"yes",
	"y",
	"correct",
	"ok",
	"okay",
	"confirm",
	"confirmed",
	"proceed",
	"looks good",
	"sure",
	"ja",
	"jo",
}
REJECTED_PHRASES = {"no", "n", "wrong", "incorrect", "cancel", "stop", "nope", "nein"}


async def await_confirmation(state: GraphState) -> dict:
	user_response = interrupt(
		{
			"message": state["confirmation_message"],
			"enhanced_query": state["enhanced_query"],
		}
	)
	normalised = str(user_response).strip().lower()
	if normalised in CONFIRMED_PHRASES:
		status = "confirmed"
	elif normalised in REJECTED_PHRASES:
		status = "rejected"
	else:
		status = "rephrased"

	new_retry = state["retry_count"] + (0 if status == "confirmed" else 1)
	result: dict = {"confirmation_status": status, "retry_count": new_retry}
	if status == "rephrased":
		result["messages"] = state["messages"] + [HumanMessage(content=str(user_response))]
	return result


instrument_module_functions(
	globals(),
	logging.getLogger("smtdb.nodes.confirm"),
	exclude={"instrument_module_functions"},
	include={"await_confirmation"},
)

