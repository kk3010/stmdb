from __future__ import annotations

import json
import logging

from app.logging_utils import instrument_module_functions

SYSTEM_CLASSIFY_INTENT = """
Classify user input into one intent:
- metadata: asks about columns/schema/allowed values/business meaning
- db_query: asks for records/aggregates from cost_centers
- out_of_scope: unrelated to cost center data

If unsure between metadata and db_query, choose db_query.

Return ONLY valid JSON with keys: intent, confidence, reason.
""".strip()


SYSTEM_ENHANCE_QUERY = """
You map natural language to schema-grounded query intent.
NEVER invent column names not present in the schema context.
Use allowed_values strings EXACTLY as listed - case-sensitive.

Return ONLY valid JSON:
{"enhanced_query":str, "confirmation_message":str, "columns_used":[str], "confidence":float}

confirmation_message rules:
- natural language only (no SQL)
- include verbatim filters, e.g. Status = INACTIVE
- end with: Shall I proceed? (yes / no / rephrase)
""".strip()


SYSTEM_BUILD_SQL = """
Generate PostgreSQL SQL from the enhanced query and schema context.
Return ONLY the raw SQL - no markdown, no explanation.
Do NOT add a LIMIT clause.
SELECT only - no INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE.
Use exact column names and table name from the schema context.
Use allowed_values strings exactly as listed.
""".strip()


SYSTEM_HUMANIZE = """
Summarize query results for finance users.
Use human_label names in summary, never raw column_name.
If row_count equals max_result_rows, note results may be truncated.
Return ONLY valid JSON: {"summary":str, "column_labels":{column_name:human_label}}
""".strip()


SYSTEM_ANSWER_FROM_DOCS = """
Answer using only the provided documentation context.
Do not invent or assume information not present in the context.
If the answer is not in the context, say so.
""".strip()


def build_classify_prompt(user_message: str) -> tuple[str, list[dict]]:
	return (SYSTEM_CLASSIFY_INTENT, [{"role": "user", "content": user_message}])


def build_enhance_prompt(user_query: str, column_docs: list[dict]) -> tuple[str, list[dict]]:
	schema_context = [
		{
			"column_name": c.get("column_name"),
			"human_label": c.get("human_label"),
			"data_type": c.get("data_type"),
			"allowed_values": c.get("allowed_values"),
			"description": c.get("description"),
		}
		for c in column_docs
	]
	content = f"User query: {user_query}\nSchema context:\n{json.dumps(schema_context, ensure_ascii=False)}"
	return (SYSTEM_ENHANCE_QUERY, [{"role": "user", "content": content}])


def build_sql_prompt(enhanced_query: str, table_name: str, column_docs: list[dict]) -> tuple[str, list[dict]]:
	content = (
		f"Enhanced query: {enhanced_query}\n"
		f"Table name: {table_name}\n"
		f"Schema context: {json.dumps(column_docs, ensure_ascii=False)}"
	)
	return (SYSTEM_BUILD_SQL, [{"role": "user", "content": content}])


def build_humanize_prompt(
	sql: str,
	db_results: list[dict],
	column_docs: list[dict],
	max_rows: int,
) -> tuple[str, list[dict]]:
	payload = {
		"sql": sql,
		"row_count": len(db_results),
		"max_result_rows": max_rows,
		"column_docs": column_docs,
		"rows": db_results[:20],
	}
	return (SYSTEM_HUMANIZE, [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])


def build_docs_prompt(user_query: str, column_docs: list[dict]) -> tuple[str, list[dict]]:
	content = f"Question: {user_query}\nContext: {json.dumps(column_docs, ensure_ascii=False)}"
	return (SYSTEM_ANSWER_FROM_DOCS, [{"role": "user", "content": content}])


instrument_module_functions(globals(), logging.getLogger("smtdb.prompts"), exclude={"instrument_module_functions"})
