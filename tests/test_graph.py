from __future__ import annotations

from app.graph import build_graph, get_graph


def test_graph_compiles_without_error():
	assert build_graph() is not None


def test_graph_has_all_eight_nodes():
	g = build_graph()
	node_names = set(g.get_graph().nodes.keys())
	for name in [
		"classify_intent",
		"retrieve_docs",
		"answer_from_docs",
		"map_columns",
		"enhance_query",
		"await_confirmation",
		"build_and_run_sql",
		"humanize_response",
	]:
		assert name in node_names


def test_get_graph_is_singleton():
	assert get_graph() is get_graph()
