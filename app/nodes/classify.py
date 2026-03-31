from __future__ import annotations

import json
import logging
import re

from app.prompts import build_classify_prompt
from app.state import VALID_INTENTS, GraphState
from app.tools.llm import chat_complete
from app.logging_utils import instrument_module_functions

logger = logging.getLogger("smtdb.nodes.classify")


def _parse_json_object(text: str) -> dict | None:
	try:
		return json.loads(text)
	except json.JSONDecodeError:
		pass

	fenced = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
	try:
		return json.loads(fenced)
	except json.JSONDecodeError:
		pass

	match = re.search(r"\{.*\}", text, flags=re.DOTALL)
	if not match:
		return None
	try:
		return json.loads(match.group(0))
	except json.JSONDecodeError:
		return None


async def classify_intent(state: GraphState) -> dict:
	messages = state.get("messages") or []
	if not messages:
		return {"error": "Session state lost. Please start a new conversation."}
	last_message = messages[-1].content
	system, messages = build_classify_prompt(str(last_message))
	try:
		response = await chat_complete(system, messages)
	except RuntimeError:
		return {"error": "The AI service is temporarily unavailable. Please try again."}

	parsed = _parse_json_object(response)
	if parsed is None:
		return {"error": "Could not understand your request. Please try again."}

	intent = parsed.get("intent", "db_query")
	if intent not in VALID_INTENTS:
		logger.warning("Unknown intent '%s'; defaulting to db_query", intent)
		intent = "db_query"

	if intent == "out_of_scope":
		return {
			"intent": "out_of_scope",
			"final_response": (
				"I can only answer questions about cost center data. "
				"Please ask about cost centers, their status, responsible "
				"persons, regions, budgets, or departments."
			),
		}

	return {"intent": intent}


instrument_module_functions(
	globals(),
	logger,
	exclude={"instrument_module_functions"},
	include={"classify_intent"},
)
