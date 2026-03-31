from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.logging_utils import instrument_module_functions
from app.nodes.classify import classify_intent
from app.nodes.confirm import await_confirmation
from app.nodes.enhance import enhance_query
from app.nodes.humanize import humanize_response
from app.nodes.map_columns import map_columns
from app.nodes.retrieve import answer_from_docs, retrieve_docs
from app.nodes.sql import build_and_run_sql
from app.state import MAX_RETRIES, GraphState

_graph = None


def route_intent(state: GraphState) -> str:
	if state.get("error"):
		return END
	if state.get("final_response"):
		return END
	if state.get("intent") == "metadata":
		return "retrieve_docs"
	if state.get("intent") == "db_query":
		return "map_columns"
	return END


def route_confirmation(state: GraphState) -> str:
	if state.get("error"):
		return END
	if state.get("confirmation_status") == "confirmed":
		return "build_and_run_sql"
	if (state.get("retry_count") or 0) >= MAX_RETRIES:
		state["final_response"] = "I'm having trouble understanding. Please try rephrasing from scratch."
		return END
	if state.get("confirmation_status") == "rephrased":
		return "map_columns"
	if state.get("confirmation_status") == "rejected":
		return "enhance_query"
	return END


def build_graph():
	graph = StateGraph(GraphState)

	graph.add_node("classify_intent", classify_intent)
	graph.add_node("retrieve_docs", retrieve_docs)
	graph.add_node("answer_from_docs", answer_from_docs)
	graph.add_node("map_columns", map_columns)
	graph.add_node("enhance_query", enhance_query)
	graph.add_node("await_confirmation", await_confirmation)
	graph.add_node("build_and_run_sql", build_and_run_sql)
	graph.add_node("humanize_response", humanize_response)

	graph.add_edge(START, "classify_intent")
	graph.add_conditional_edges("classify_intent", route_intent)

	graph.add_edge("retrieve_docs", "answer_from_docs")
	graph.add_edge("answer_from_docs", END)

	graph.add_edge("map_columns", "enhance_query")
	graph.add_edge("enhance_query", "await_confirmation")
	graph.add_conditional_edges("await_confirmation", route_confirmation)

	graph.add_edge("build_and_run_sql", "humanize_response")
	graph.add_edge("humanize_response", END)

	checkpointer = InMemorySaver()
	return graph.compile(checkpointer=checkpointer)


def get_graph():
	global _graph
	if _graph is None:
		_graph = build_graph()
	return _graph


instrument_module_functions(globals(), logging.getLogger("smtdb.graph"), exclude={"instrument_module_functions"})
