# Speak To My Database 

A natural-language chat interface for querying cost center data in PostgreSQL. Finance and controlling teams can ask questions in plain English and get accurate, human-readable answers — no SQL required.

Built with **LangGraph 1.1 · Claude Sonnet 4.6 · Voyage AI · ChromaDB · Streamlit**.

---

## How it works

Every question goes through a structured agentic pipeline before anything touches the database:

1. **Intent classification** — is this a question about the data, or about what a column means?
2. **Column mapping** — user terminology is matched to real PostgreSQL column names via Voyage AI semantic similarity search over the column documentation
3. **Confirmation** — the system shows a plain-language interpretation of the query and waits for explicit confirmation before generating any SQL (filter values shown verbatim, e.g. `Status = INACTIVE`)
4. **SQL generation & execution** — a validated `SELECT` statement is built, checked with `sqlglot`, and run against `smtdb`
5. **Human-friendly response** — results are returned as a short summary plus a structured table with human-readable column headers

```
User query
    │
    ▼
classify_intent ──► [metadata] ──► retrieve_docs ──► answer_from_docs ──► END
    │
    ▼ [db_query]
map_columns ──► enhance_query ──► await_confirmation ──► [rejected]  ──► enhance_query (max 3×)
                                        │                  [rephrased] ──► map_columns (fresh retrieval)
                                        ▼ [confirmed]
                                 build_and_run_sql ──► humanize_response ──► END
```

---

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- PostgreSQL running locally
- [Anthropic API key](https://console.anthropic.com) (free tier is sufficient)
- [Voyage AI API key](https://dash.voyageai.com) (free tier is sufficient)

---

## Quick start

```bash
# 1. Clone
git clone <your-repo-url>
cd cc-chat

# 2. Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Install dependencies
uv sync

# 4. Configure environment
cp .env.example .env
# → edit .env with your API keys and DB credentials (see Configuration below)

# 5. Create the database and load fake data
createdb smtdb
psql -U your_user -d smtdb -f db/seed.sql

# 6. Verify API connections
make check-apis

# 7. Embed column documentation into ChromaDB
make ingest

# 8. Launch
make run
# → opens at http://localhost:8501
```

---

## Configuration

Edit `.env` after copying from `.env.example`:

```dotenv
# Anthropic Claude API  —  console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MAX_TOKENS=4096

# Voyage AI (embeddings)  —  dash.voyageai.com
VOYAGE_API_KEY=pa-...
VOYAGE_MODEL=voyage-3.5

# PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_NAME=smtdb
DB_USER=your_user
DB_PASSWORD=your_password
TABLE_NAME=cost_centers

# App
CHROMA_PATH=./chroma_db
COLUMN_DOCS_PATH=./docs/columns.json
SIMILARITY_THRESHOLD=0.75
MAX_RESULT_ROWS=500
LOG_PATH=./logs/chat.log
```

Both API keys have generous free tiers — no credit card required for a local PoC at this query volume.

---

## Database

The PoC ships with a fake dataset of 150 cost center records (`db/seed.sql`). The table has 24 columns covering identity, classification, organisation, responsibility, validity, hierarchy, financials, and audit fields.

```bash
# Load schema + data (idempotent — safe to re-run)
createdb smtdb
psql -U your_user -d smtdb -f db/seed.sql

# Verify
psql -U your_user -d smtdb \
  -c "SELECT status, COUNT(*) FROM cost_centers GROUP BY status ORDER BY status;"
```

Expected output:
```
 status   | count
----------+-------
 ACTIVE   |   103
 BLOCKED  |    12
 INACTIVE |    35
```

The dataset uses SAP-style cost center codes (`KS-FIN-0001`), German person names, German/Austrian/Swiss region codes (`DE-BY`, `AT-WI`, `CH-ZH`), and EUR financials.

---

## Column documentation

`docs/columns.json` documents all 24 columns of `cost_centers` and is the system's single source of truth for both ChromaDB semantic search and SQL generation.

Each entry follows this schema:

```json
{
  "column_name":   "status",
  "human_label":   "Status",
  "data_type":     "VARCHAR",
  "nullable":      false,
  "allowed_values": ["ACTIVE", "INACTIVE", "BLOCKED"],
  "description":   "Current operational status of the cost center...",
  "example_values": ["ACTIVE", "INACTIVE"]
}
```

> **`allowed_values` is the most critical field.** These exact strings are used verbatim in `WHERE` clauses. A user asking for "inactive cost centers" will generate `WHERE status = 'INACTIVE'` — correct only because `allowed_values` lists `"INACTIVE"` in uppercase. Wrong or missing values cause silent zero-row results.

After editing `columns.json`, re-run `make ingest-force` to rebuild the ChromaDB collection.

---

## Project structure

```
stmdb/
├── app/
│   ├── config.py          # pydantic-settings — reads .env
│   ├── state.py           # GraphState TypedDict + constants
│   ├── prompts.py         # system prompts + builder functions
│   ├── graph.py           # LangGraph StateGraph assembly
│   ├── nodes/
│   │   ├── classify.py    # classify_intent
│   │   ├── retrieve.py    # retrieve_docs + answer_from_docs (metadata path)
│   │   ├── map_columns.py # column similarity search (db_query path)
│   │   ├── enhance.py     # enhance_query — rewrites with real column names
│   │   ├── confirm.py     # await_confirmation — LangGraph interrupt()
│   │   ├── sql.py         # build_and_run_sql — generate, validate, execute
│   │   └── humanize.py    # humanize_response — summary + column label map
│   └── tools/
│       ├── llm.py         # AsyncAnthropic + Voyage AI singletons
│       ├── chroma.py      # ChromaDB ingestion + similarity search
│       └── postgres.py    # asyncpg query execution
├── db/
│   └── seed.sql           # DDL + 150-row fake dataset (idempotent)
├── docs/
│   └── columns.json       # 24-column documentation — edit this, then make ingest-force
├── logs/                  # auto-created at runtime
├── scripts/
│   └── check_apis.py      # API connectivity check
├── tests/
│   ├── conftest.py        # shared fixtures (mock clients, sample columns)
│   ├── test_*.py          # one test file per phase
│   └── integration/
│       └── test_e2e.py    # full pipeline tests (requires RUN_INTEGRATION=1)
├── streamlit_app.py       # Streamlit entry point
├── Makefile               # all common commands
├── .env                   # credentials — never committed
├── .env.example           # template — committed, no real values
├── .python-version        # 3.12
├── pyproject.toml
└── uv.lock                # committed — pin exact dependency versions
```

---

## Tech stack

| Layer | Technology | Version |
|---|---|---|
| Agent framework | LangGraph | 1.1 |
| LLM | Anthropic Claude Sonnet 4.6 | `claude-sonnet-4-6` |
| LLM SDK | `anthropic` | 0.86.0 |
| Embeddings | Voyage AI `voyage-3.5` | current |
| Embedding SDK | `voyageai` | current |
| Vector store | ChromaDB | 1.5.5 |
| Database driver | asyncpg | 0.31.0 |
| SQL validator | sqlglot | 29.0.1 |
| UI | Streamlit | 1.55.0 |
| Config | pydantic-settings | 2.13.1 |
| Python | CPython | 3.12+ |

**Why Claude Sonnet 4.6?** 1M token context window at standard pricing, purpose-built for agentic multi-step workflows, reliable tool use and instruction following. Upgrade to Opus 4.6 by changing `CLAUDE_MODEL=claude-opus-4-6` in `.env` — no code changes needed.

**Why Voyage AI?** Anthropic's officially recommended embedding provider. The `input_type` parameter (`"document"` at ingestion, `"query"` at search time) improves retrieval precision for RAG use cases. Free tier easily covers PoC usage.

---

## Example queries

| User input | Intent | What happens |
|---|---|---|
| `Who is responsible for cost center KS-FIN-0003?` | `db_query` | Maps to `cc_code` + `responsible_person`, confirms, runs SELECT |
| `Show me all inactive cost centers` | `db_query` | Maps to `status = 'INACTIVE'`, confirms with verbatim value, runs SELECT |
| `Which cost centers in Bayern are over budget?` | `db_query` | Maps to `region_code = 'DE-BY'` + `actual_eur > budget_eur`, confirms, runs SELECT |
| `How many IT department cost centers are there?` | `db_query` | Maps to `org_unit_code = 'IT'`, generates COUNT query |
| `What does the Status column mean?` | `metadata` | Retrieves from ChromaDB docs — no SQL |
| `What values can the Status column have?` | `metadata` | Returns `ACTIVE`, `INACTIVE`, `BLOCKED` from `allowed_values` — no SQL |
| `What's the weather in Munich?` | `out_of_scope` | Canned response, no SQL |

---

## Make commands

```bash
make run           # launch Streamlit at http://localhost:8501
make test          # run unit tests (no API keys needed)
make test-all      # run all tests including integration (needs RUN_INTEGRATION=1)
make check-apis    # verify Anthropic + Voyage AI connections
make ingest        # embed docs/columns.json into ChromaDB (skips if already done)
make ingest-force  # force re-embed (use after editing columns.json)
make status        # show ChromaDB collection document count
make lint          # ruff check
make format        # ruff format
make typecheck     # mypy
```

---

## Development

```bash
# Add a dependency
uv add some-package

# Sync after pulling (picks up uv.lock changes from teammates)
uv sync

# Run a single test file
uv run pytest tests/test_postgres.py -v

# Run integration tests against real smtdb and APIs
RUN_INTEGRATION=1 uv run pytest tests/integration/ -v
```

---

## Safety

- Only `SELECT` statements ever reach the database. Every generated SQL query is validated with `sqlglot` before execution — any DDL or DML (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `TRUNCATE`, `ALTER`) is rejected before connecting to PostgreSQL.
- No SQL runs without explicit user confirmation.
- Results are hard-capped at 500 rows.
- All API keys and database credentials live in `.env` only — never in code and never committed to git.
- Raw exception messages are never shown to the user — all errors are friendly English sentences. Full errors are logged to `logs/chat.log`.

---

## Logs

All node transitions, generated SQL, similarity scores, and row counts are written to `logs/chat.log`. This is the primary debugging tool — when a query returns unexpected results, the log shows exactly what SQL was generated and which columns were matched.

```bash
tail -f logs/chat.log
```

---

## Enabling conversational memory (post-PoC)

The graph state is persisted per session via LangGraph's checkpointer. Enabling multi-turn memory across sessions requires one change in `app/graph.py`:

```python
# PoC — in-memory, no cross-session persistence
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string(":memory:")

# Production — persistent memory per user session
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
checkpointer = AsyncPostgresSaver.from_conn_string(settings.db_url)
```

No graph changes required.

---

## Connecting to production data

To switch from the fake dataset to the real database:

1. Update `DB_*` env vars in `.env` to point at the production instance.
2. Update `TABLE_NAME` to the real table name.
3. Replace `docs/columns.json` with documentation for the real table's columns.
4. Run `make ingest-force` to rebuild the ChromaDB collection.

No code changes required.

---

## Status

Local PoC. See [`docs/project_requirements.md`](docs/project_requirements.md) for the full specification and production upgrade path.