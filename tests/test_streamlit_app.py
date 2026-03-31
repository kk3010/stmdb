from __future__ import annotations

from streamlit.testing.v1 import AppTest

from streamlit_app import _build_dataframe


def test_app_loads_without_exception():
	app = AppTest.from_file("streamlit_app.py")
	app.run()
	assert not app.exception


def test_app_has_title_cost_center_chat():
	app = AppTest.from_file("streamlit_app.py")
	app.run()
	assert any("Cost Center Chat" in str(t.value) for t in app.title)


def test_app_initialises_thread_id_as_uuid4():
	app = AppTest.from_file("streamlit_app.py")
	app.run()
	thread_id = app.session_state["thread_id"]
	assert len(thread_id) == 36
	assert thread_id.count("-") == 4


def test_app_initialises_awaiting_confirmation_false():
	app = AppTest.from_file("streamlit_app.py")
	app.run()
	assert app.session_state["awaiting_confirmation"] is False


def test_app_has_chat_input():
	app = AppTest.from_file("streamlit_app.py")
	app.run()
	assert app.chat_input is not None


def test_build_dataframe_renames_to_human_labels(sample_columns):
	df = _build_dataframe([{"status": "ACTIVE", "budget_eur": "150000.00"}], sample_columns)
	assert "Status" in df.columns
	assert "Budget (EUR)" in df.columns
	assert "status" not in df.columns


def test_build_dataframe_falls_back_for_unmapped_columns(sample_columns):
	df = _build_dataframe([{"unknown_col": "x"}], sample_columns)
	assert "unknown_col" in df.columns
