.PHONY: run test test-all lint format typecheck check-apis ingest ingest-force status

run:
	uv run streamlit run streamlit_app.py

test:
	uv run pytest tests/ -v --ignore=tests/integration

test-all:
	RUN_INTEGRATION=1 uv run pytest tests/ -v

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy app/

check-apis:
	uv run python scripts/check_apis.py

ingest:
	uv run python -m app.tools.chroma ingest

ingest-force:
	uv run python -m app.tools.chroma ingest --force

status:
	uv run python -m app.tools.chroma status
