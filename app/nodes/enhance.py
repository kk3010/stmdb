from __future__ import annotations

import json
import logging
import re

from app.prompts import build_enhance_prompt
from app.state import GraphState
from app.tools.llm import chat_complete
from app.logging_utils import instrument_module_functions

logger = logging.getLogger("smtdb.nodes.enhance")


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


def _fallback_confirmation_message(user_query: str, enhanced_query: str | None) -> str:
	text = f"{user_query} {enhanced_query or ''}".lower()
	cc_match = re.search(r"KS-[A-Z&]+-\d{4}", f"{user_query} {enhanced_query or ''}", re.IGNORECASE)
	cc_code = cc_match.group(0).upper() if cc_match else None

	is_contact_query = any(k in text for k in ["contact", "responsible", "who", "manage", "owner"])
	if is_contact_query and cc_code:
		return (
			"You are inquiring information about the Responsible Person for "
			f"the Cost Center Code {cc_code}, is this correct?\n\n"
			"Shall I proceed? (yes / no / rephrase)"
		)

	if cc_code:
		return (
			f"You are asking about Cost Center Code {cc_code}. "
			"Shall I proceed? (yes / no / rephrase)"
		)

	return "Please confirm my interpretation. Shall I proceed? (yes / no / rephrase)"


def _contact_query_override(user_query: str) -> tuple[str, str] | None:
	text = user_query.lower()
	cc_match = re.search(r"KS-[A-Z&]+-\d{4}", user_query, re.IGNORECASE)
	if not cc_match:
		return None
	cc_code = cc_match.group(0).upper()
	is_contact_query = any(k in text for k in ["contact", "responsible", "who", "manage", "owner"])
	if not is_contact_query:
		return None

	enhanced_query = (
		"Show responsible person details for cost center "
		f"where cc_code = '{cc_code}' using responsible_person, deputy_person, and controlling_person"
	)
	confirmation = (
		"You are inquiring information about the Responsible Person for "
		f"the Cost Center Code {cc_code}, is this correct?\n\n"
		"Shall I proceed? (yes / no / rephrase)"
	)
	return enhanced_query, confirmation


async def enhance_query(state: GraphState) -> dict:
	last_message = str(state["messages"][-1].content)
	system, messages = build_enhance_prompt(last_message, state["retrieved_col_docs"])
	try:
		response = await chat_complete(system, messages)
	except RuntimeError:
		return {"error": "Could not interpret your query. Please try rephrasing."}

	parsed = _parse_json_object(response)
	if parsed is None:
		return {"error": "Could not interpret your query. Please try rephrasing."}

	available_columns = {doc.get("column_name") for doc in state["retrieved_col_docs"]}
	for col in parsed.get("columns_used", []):
		if col not in available_columns:
			logger.warning("Column '%s' in columns_used not in retrieved docs", col)

	override = _contact_query_override(last_message)
	if override is not None:
		enhanced_query, confirmation_message = override
	else:
		enhanced_query = parsed.get("enhanced_query")
		confirmation_message = parsed.get("confirmation_message")

	if not confirmation_message:
		confirmation_message = _fallback_confirmation_message(
			last_message,
			parsed.get("enhanced_query"),
		)

	return {
		"enhanced_query": enhanced_query,
		"confirmation_message": confirmation_message,
		"retry_count": state["retry_count"],
	}


instrument_module_functions(globals(), logger, exclude={"instrument_module_functions"})

