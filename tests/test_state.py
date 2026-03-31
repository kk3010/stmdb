from __future__ import annotations

from app.state import MAX_RETRIES, VALID_INTENTS, initial_state


def test_graph_state_has_exactly_11_fields():
	s = initial_state("hello")
	assert len(s.keys()) == 11


def test_valid_intents_is_frozenset_of_three():
	assert isinstance(VALID_INTENTS, frozenset)
	assert VALID_INTENTS == frozenset({"metadata", "db_query", "out_of_scope"})


def test_max_retries_is_three():
	assert MAX_RETRIES == 3


def test_initial_state_has_one_human_message():
	s = initial_state("hello")
	assert len(s["messages"]) == 1
	assert s["messages"][0].content == "hello"


def test_initial_state_all_optional_fields_are_none():
	s = initial_state("hello")
	assert s["intent"] is None
	assert s["enhanced_query"] is None
	assert s["confirmation_message"] is None
	assert s["confirmation_status"] is None
	assert s["sql"] is None
	assert s["db_results"] is None
	assert s["final_response"] is None
	assert s["error"] is None


def test_initial_state_retry_count_is_zero():
	assert initial_state("hello")["retry_count"] == 0


def test_initial_state_retrieved_col_docs_is_empty_list():
	assert initial_state("hello")["retrieved_col_docs"] == []
