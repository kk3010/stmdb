from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage


def _state(msg: str = "hello"):
	return {
		"messages": [HumanMessage(content=msg)],
		"intent": None,
		"retrieved_col_docs": [],
		"enhanced_query": None,
		"confirmation_message": None,
		"confirmation_status": None,
		"sql": None,
		"db_results": None,
		"final_response": None,
		"error": None,
		"retry_count": 0,
	}


@pytest.mark.asyncio
async def test_classify_returns_db_query(mocker):
	from app.nodes.classify import classify_intent

	mocker.patch("app.nodes.classify.chat_complete", mocker.AsyncMock(return_value='{"intent":"db_query"}'))
	res = await classify_intent(_state())
	assert res["intent"] == "db_query"


@pytest.mark.asyncio
async def test_classify_falls_back_on_unknown_intent(mocker):
	from app.nodes.classify import classify_intent

	mocker.patch("app.nodes.classify.chat_complete", mocker.AsyncMock(return_value='{"intent":"x"}'))
	res = await classify_intent(_state())
	assert res["intent"] == "db_query"


@pytest.mark.asyncio
async def test_classify_out_of_scope_sets_final_response(mocker):
	from app.nodes.classify import classify_intent

	mocker.patch("app.nodes.classify.chat_complete", mocker.AsyncMock(return_value='{"intent":"out_of_scope"}'))
	res = await classify_intent(_state())
	assert res["intent"] == "out_of_scope"
	assert res["final_response"]


@pytest.mark.asyncio
async def test_classify_api_error_returns_friendly_error(mocker):
	from app.nodes.classify import classify_intent

	mocker.patch("app.nodes.classify.chat_complete", mocker.AsyncMock(side_effect=RuntimeError("x")))
	res = await classify_intent(_state())
	assert "error" in res


@pytest.mark.asyncio
async def test_classify_malformed_json_returns_error(mocker):
	from app.nodes.classify import classify_intent

	mocker.patch("app.nodes.classify.chat_complete", mocker.AsyncMock(return_value="not json"))
	res = await classify_intent(_state())
	assert "error" in res


@pytest.mark.asyncio
async def test_map_columns_returns_docs(mocker, sample_columns):
	from app.nodes.map_columns import map_columns

	mocker.patch("app.nodes.map_columns.search_columns", mocker.AsyncMock(return_value=sample_columns))
	res = await map_columns(_state())
	assert len(res["retrieved_col_docs"]) == 5


@pytest.mark.asyncio
async def test_map_columns_error_on_search_failure(mocker):
	from app.nodes.map_columns import map_columns

	mocker.patch("app.nodes.map_columns.search_columns", mocker.AsyncMock(side_effect=RuntimeError("x")))
	res = await map_columns(_state())
	assert "error" in res


@pytest.mark.asyncio
async def test_enhance_returns_confirmation_with_verbatim_inactive(mocker, sample_columns):
	from app.nodes.enhance import enhance_query

	s = _state("inactive")
	s["retrieved_col_docs"] = sample_columns
	mocker.patch(
		"app.nodes.enhance.chat_complete",
		mocker.AsyncMock(return_value='{"enhanced_query":"q","confirmation_message":"Status = INACTIVE. Shall I proceed? (yes / no / rephrase)","columns_used":["status"],"confidence":0.9}'),
	)
	res = await enhance_query(s)
	assert "INACTIVE" in res["confirmation_message"]


@pytest.mark.asyncio
async def test_enhance_malformed_json_returns_error(mocker, sample_columns):
	from app.nodes.enhance import enhance_query

	s = _state()
	s["retrieved_col_docs"] = sample_columns
	mocker.patch("app.nodes.enhance.chat_complete", mocker.AsyncMock(return_value="oops"))
	res = await enhance_query(s)
	assert "error" in res


@pytest.mark.asyncio
async def test_yes_is_confirmed(mocker):
	from app.nodes.confirm import await_confirmation

	mocker.patch("app.nodes.confirm.interrupt", return_value="yes")
	s = _state()
	res = await await_confirmation(s)
	assert res["confirmation_status"] == "confirmed"
	assert res["retry_count"] == 0


@pytest.mark.asyncio
async def test_no_is_rejected_and_increments_retry(mocker):
	from app.nodes.confirm import await_confirmation

	mocker.patch("app.nodes.confirm.interrupt", return_value="no")
	s = _state()
	res = await await_confirmation(s)
	assert res["confirmation_status"] == "rejected"
	assert res["retry_count"] == 1


@pytest.mark.asyncio
async def test_new_query_text_is_rephrased_and_increments_retry(mocker):
	from app.nodes.confirm import await_confirmation

	mocker.patch("app.nodes.confirm.interrupt", return_value="try for IT")
	s = _state()
	res = await await_confirmation(s)
	assert res["confirmation_status"] == "rephrased"
	assert res["retry_count"] == 1


@pytest.mark.asyncio
async def test_rephrased_appends_new_human_message(mocker):
	from app.nodes.confirm import await_confirmation

	mocker.patch("app.nodes.confirm.interrupt", return_value="new message")
	s = _state()
	res = await await_confirmation(s)
	assert res["messages"][-1].content == "new message"


@pytest.mark.asyncio
async def test_ja_is_confirmed(mocker):
	from app.nodes.confirm import await_confirmation

	mocker.patch("app.nodes.confirm.interrupt", return_value="ja")
	res = await await_confirmation(_state())
	assert res["confirmation_status"] == "confirmed"


@pytest.mark.asyncio
async def test_sql_strips_backtick_fences(mocker, sample_columns):
	from app.nodes.sql import build_and_run_sql

	s = _state()
	s["enhanced_query"] = "q"
	s["retrieved_col_docs"] = sample_columns
	mocker.patch("app.nodes.sql.chat_complete", mocker.AsyncMock(return_value="```sql\nSELECT * FROM cost_centers\n```"))
	mocker.patch("app.nodes.sql.execute_query", mocker.AsyncMock(return_value=[]))
	res = await build_and_run_sql(s)
	assert res["sql"] == "SELECT * FROM cost_centers"


@pytest.mark.asyncio
async def test_sql_strips_uppercase_fence(mocker, sample_columns):
	from app.nodes.sql import build_and_run_sql

	s = _state()
	s["enhanced_query"] = "q"
	s["retrieved_col_docs"] = sample_columns
	mocker.patch("app.nodes.sql.chat_complete", mocker.AsyncMock(return_value="```SQL\nSELECT 1\n```"))
	mocker.patch("app.nodes.sql.execute_query", mocker.AsyncMock(return_value=[]))
	res = await build_and_run_sql(s)
	assert res["sql"] == "SELECT 1"


@pytest.mark.asyncio
async def test_sql_rejects_delete_from_llm(mocker, sample_columns):
	from app.nodes.sql import build_and_run_sql

	s = _state()
	s["enhanced_query"] = "q"
	s["retrieved_col_docs"] = sample_columns
	mocker.patch("app.nodes.sql.chat_complete", mocker.AsyncMock(return_value="DELETE FROM cost_centers"))
	res = await build_and_run_sql(s)
	assert res.get("sql") is None


@pytest.mark.asyncio
async def test_sql_returns_results_and_stores_sql(mocker, sample_columns):
	from app.nodes.sql import build_and_run_sql

	s = _state()
	s["enhanced_query"] = "q"
	s["retrieved_col_docs"] = sample_columns
	mocker.patch("app.nodes.sql.chat_complete", mocker.AsyncMock(return_value="SELECT 1"))
	mocker.patch("app.nodes.sql.execute_query", mocker.AsyncMock(return_value=[{"a": 1}]))
	res = await build_and_run_sql(s)
	assert res["sql"] == "SELECT 1"
	assert res["db_results"] == [{"a": 1}]


@pytest.mark.asyncio
async def test_empty_results_mentions_case_sensitivity(mocker):
	from app.nodes.humanize import humanize_response

	s = _state()
	s["db_results"] = []
	res = await humanize_response(s)
	assert "INACTIVE" in res["final_response"] or "case" in res["final_response"].lower()


@pytest.mark.asyncio
async def test_humanize_returns_summary(mocker, sample_columns):
	from app.nodes.humanize import humanize_response

	s = _state()
	s["db_results"] = [{"status": "INACTIVE"}] * 35
	s["retrieved_col_docs"] = sample_columns
	s["sql"] = "SELECT"
	mocker.patch("app.nodes.humanize.chat_complete", mocker.AsyncMock(return_value='{"summary":"Found 35 rows","column_labels":{}}'))
	res = await humanize_response(s)
	assert "35" in res["final_response"]


@pytest.mark.asyncio
async def test_humanize_fallback_on_malformed_json(mocker, sample_columns):
	from app.nodes.humanize import humanize_response

	s = _state()
	s["db_results"] = [{"a": 1}]
	s["retrieved_col_docs"] = sample_columns
	s["sql"] = "SELECT"
	mocker.patch("app.nodes.humanize.chat_complete", mocker.AsyncMock(return_value="raw response"))
	res = await humanize_response(s)
	assert res["final_response"] == "raw response"
