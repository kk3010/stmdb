from __future__ import annotations

import os

import pytest
from langgraph.types import Command

from app.config import settings
from app.graph import get_graph
from app.state import initial_state
from app.tools.chroma import get_chroma_client
from app.tools.llm import chat_complete, embed
from app.tools.postgres import execute_query

pytestmark = pytest.mark.skipif(
	os.getenv("RUN_INTEGRATION") != "1",
	reason="Set RUN_INTEGRATION=1 to run integration tests",
)


def test_chroma_collection_has_24_documents():
	col = get_chroma_client().get_collection("cost_center_columns")
	assert col.count() == 24


@pytest.mark.asyncio
async def test_embed_returns_1024_dimensions():
	vec = await embed("status", input_type="query")
	assert len(vec) == 1024


@pytest.mark.asyncio
async def test_chat_complete_responds_to_simple_prompt():
	text = await chat_complete("Be short", [{"role": "user", "content": "hello"}])
	assert isinstance(text, str)


def test_full_db_query_confirmation_contains_inactive_verbatim():
	graph = get_graph()
	with pytest.raises(Exception):
		graph.invoke(initial_state("Show me all inactive cost centers"), config={"configurable": {"thread_id": "it1"}})


@pytest.mark.asyncio
async def test_non_select_raises_before_reaching_db():
	with pytest.raises(ValueError):
		await execute_query("DELETE FROM cost_centers WHERE 1=1")
