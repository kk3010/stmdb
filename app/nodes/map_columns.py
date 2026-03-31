from __future__ import annotations

import logging

from app.state import GraphState
from app.tools.chroma import search_columns
from app.logging_utils import instrument_module_functions


async def map_columns(state: GraphState) -> dict:
	try:
		docs = await search_columns(str(state["messages"][-1].content))
		return {"retrieved_col_docs": docs}
	except RuntimeError:
		return {"error": "Could not search column documentation. Run 'make ingest' first."}


instrument_module_functions(globals(), logging.getLogger("smtdb.nodes.map_columns"), exclude={"instrument_module_functions"})

