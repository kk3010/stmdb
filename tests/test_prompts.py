from __future__ import annotations

from app import prompts


def test_system_classify_contains_all_three_intents():
	p = prompts.SYSTEM_CLASSIFY_INTENT
	assert "metadata" in p
	assert "db_query" in p
	assert "out_of_scope" in p


def test_system_classify_requests_json_with_required_fields():
	p = prompts.SYSTEM_CLASSIFY_INTENT
	assert "intent" in p
	assert "confidence" in p
	assert "reason" in p


def test_system_classify_mentions_db_query_as_default():
	assert "choose db_query" in prompts.SYSTEM_CLASSIFY_INTENT


def test_build_classify_prompt_returns_tuple_with_user_message():
	system, messages = prompts.build_classify_prompt("hello")
	assert isinstance(system, str)
	assert messages[0]["content"] == "hello"


def test_system_enhance_forbids_invented_columns():
	assert "NEVER invent column names" in prompts.SYSTEM_ENHANCE_QUERY


def test_system_enhance_requires_verbatim_allowed_values():
	assert "EXACTLY as listed" in prompts.SYSTEM_ENHANCE_QUERY


def test_build_enhance_prompt_includes_status_allowed_values(sample_columns):
	_, messages = prompts.build_enhance_prompt("inactive", sample_columns)
	assert "ACTIVE" in messages[0]["content"]


def test_system_sql_forbids_limit():
	assert "Do NOT add a LIMIT" in prompts.SYSTEM_BUILD_SQL


def test_system_sql_forbids_markdown():
	assert "no markdown" in prompts.SYSTEM_BUILD_SQL.lower()


def test_system_sql_forbids_all_dml_keywords():
	lower = prompts.SYSTEM_BUILD_SQL.lower()
	for kw in ["insert", "update", "delete", "drop", "alter", "truncate"]:
		assert kw in lower


def test_build_sql_prompt_includes_table_name(sample_columns):
	_, messages = prompts.build_sql_prompt("q", "cost_centers", sample_columns)
	assert "cost_centers" in messages[0]["content"]


def test_build_humanize_prompt_includes_row_count(sample_columns):
	_, messages = prompts.build_humanize_prompt("SELECT", [{"a": 1}] * 7, sample_columns, 500)
	assert "7" in messages[0]["content"]


def test_build_humanize_prompt_truncates_to_20_rows(sample_columns):
	_, messages = prompts.build_humanize_prompt("SELECT", [{"a": 1}] * 100, sample_columns, 500)
	assert messages[0]["content"].count('"a": 1') <= 20


def test_system_answer_from_docs_forbids_hallucination():
	assert "Do not invent" in prompts.SYSTEM_ANSWER_FROM_DOCS
