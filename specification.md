# Speak to My Database — PoC — GitHub Copilot Agent Implementation Specification

> **Version 1.0 — March 2026**
> Grounded in Requirements v2.0. Tech stack: Claude Sonnet 4.6 · Voyage AI voyage-3.5 · LangGraph 1.1 · ChromaDB 1.5.5 · asyncpg 0.31.0 · sqlglot 29.0.1 · Streamlit 1.55.0.

---

## Agent Rules — Read Before Starting

### Clarification Protocol

> **STOP and ask before writing code whenever:**
> - A requirement is ambiguous or has more than one valid interpretation
> - A value is not explicitly stated (column name, file path, env var name)
> - A library API differs from what this spec describes
> - Two requirements appear to conflict
> - A test is failing and the cause is unclear — do NOT silently change the test
> - You are about to make an assumption that affects more than one file

**Format every clarification request as:**
```
CLARIFICATION NEEDED — Phase X / Task Y
Question: [single specific question]
Context:  [one sentence explaining why]
Options:  [2–3 options if applicable]
```

One question per request. Wait for an explicit answer before proceeding.

### Implementation Rules

1. **Tests first, code second.** Write the test file for a task before implementing the code under test.
2. **Never start a new phase until all tests in the current phase pass.**
3. **Run the full suite after every phase:** `uv run pytest` — not just the new tests.
4. **Never commit a phase with failing tests.**
5. **Never silently change a test to make it pass** — if a test appears wrong, raise a clarification request.
6. **No hardcoded secrets or values.** Everything runtime comes from `settings`.
7. **Never expose raw exception text to the Streamlit UI.** All errors shown to users must be friendly English sentences.
8. **Document completions.** After finishing each phase, tick the checklist and append a row to the completion log at the bottom of this file.

---

## Prerequisites

Before starting Phase 0, verify all of the following are true. If any is missing, raise a clarification request.

- [ ] `uv` is installed and `uv sync` runs without error
- [ ] `docs/columns.json` exists (24 column entries)
- [ ] `db/seed.sql` exists
- [ ] PostgreSQL is running locally; `smtdb` database created; `cost_centers` table seeded
- [ ] `.env` file exists with real `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, and DB credentials
- [ ] `make check-apis` passes (Anthropic + Voyage AI both respond)

---

## Project Structure (target state)

```
stmdb/
├── app/
│   ├── __init__.py
│   ├── config.py             # pydantic-settings — reads .env
│   ├── state.py              # GraphState TypedDict + constants
│   ├── prompts.py            # system prompts + builder functions
│   ├── graph.py              # LangGraph StateGraph assembly
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── classify.py       # classify_intent
│   │   ├── retrieve.py       # retrieve_docs + answer_from_docs
│   │   ├── map_columns.py    # map_columns
│   │   ├── enhance.py        # enhance_query
│   │   ├── confirm.py        # await_confirmation (interrupt)
│   │   ├── sql.py            # build_and_run_sql
│   │   └── humanize.py       # humanize_response
│   └── tools/
│       ├── __init__.py
│       ├── llm.py            # AsyncAnthropic + Voyage AI singletons
│       ├── chroma.py         # ChromaDB ingestion + search
│       └── postgres.py       # asyncpg query execution
├── db/
│   └── seed.sql              # DDL + 150-row fake dataset
├── docs/
│   └── columns.json          # 24-column documentation
├── logs/                     # auto-created at runtime
├── scripts/
│   └── check_apis.py         # API connectivity verification
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # shared fixtures
│   ├── test_phase0_skeleton.py
│   ├── test_config.py
│   ├── test_state.py
│   ├── test_llm.py
│   ├── test_postgres.py
│   ├── test_chroma.py
│   ├── test_prompts.py
│   ├── test_nodes.py
│   ├── test_graph.py
│   ├── test_streamlit_app.py
│   ├── test_hardening.py
│   └── integration/
│       ├── __init__.py
│       └── test_e2e.py
├── streamlit_app.py
├── Makefile
├── .env                      # never committed
├── .env.example              # committed — no real values
├── .gitignore
├── .python-version           # "3.12"
├── pyproject.toml
└── uv.lock                   # committed
```

---

## Phase 0 — Skeleton & Test Infrastructure

> **Goal:** every file exists, shared fixtures are ready, test runner is configured. No logic yet.

### Task 0.1 — Create all missing files

Create every file in the target structure above as an empty file. Exception: if `docs/columns.json` or `db/seed.sql` are missing, raise a clarification request — do not create them as empty files.

### Task 0.2 — `pyproject.toml` — add test/lint config

Add the following sections. Do not modify existing fields:

```toml
[project]
requires-python = ">=3.12"
dependencies = [
    "langgraph==1.1.*",
    "langgraph-checkpoint-sqlite",
    "anthropic==0.86.0",
    "voyageai",
    "chromadb==1.5.5",
    "asyncpg==0.31.0",
    "sqlglot==29.0.1",
    "streamlit==1.55.0",
    "pydantic-settings==2.13.1",
    "python-dotenv>=1.0",
    "pandas",
]

[dependency-groups]
dev = ["pytest>=8", "pytest-asyncio", "pytest-mock", "ruff", "mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths   = ["tests"]

[tool.ruff]
line-length    = 100
target-version = "py312"

[tool.mypy]
python_version         = "3.12"
ignore_missing_imports = true
```

### Task 0.3 — `.env.example`

```dotenv
# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-your-key-here
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MAX_TOKENS=4096

# Voyage AI
VOYAGE_API_KEY=pa-your-key-here
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

### Task 0.4 — `.gitignore`

```
.env
.venv/
chroma_db/
logs/
__pycache__/
*.pyc
.ruff_cache/
.mypy_cache/
.pytest_cache/
```

### Task 0.5 — `tests/conftest.py` — shared fixtures

```python
# Implement these fixtures exactly as described.
# If any fixture behaviour is unclear, raise a clarification request.

# settings_override(monkeypatch) -> Settings
#   Patches all required env vars with safe test values:
#     ANTHROPIC_API_KEY    = "sk-ant-test-key"
#     CLAUDE_MODEL         = "claude-sonnet-4-6"
#     CLAUDE_MAX_TOKENS    = "1024"
#     VOYAGE_API_KEY       = "pa-test-key"
#     VOYAGE_MODEL         = "voyage-3.5"
#     DB_HOST              = "localhost"
#     DB_PORT              = "5432"
#     DB_NAME              = "smtdb_test"
#     DB_USER              = "test_user"
#     DB_PASSWORD          = "test_password"
#     TABLE_NAME           = "cost_centers"
#     SIMILARITY_THRESHOLD = "0.5"
#     MAX_RESULT_ROWS      = "10"
#   Returns freshly instantiated Settings() with these values.

# sample_columns() -> list[dict]
#   Returns a hardcoded list of 5 column dicts matching columns.json schema.
#   Must include:
#     - cc_code            (no allowed_values, nullable: false)
#     - status             (allowed_values: ["ACTIVE","INACTIVE","BLOCKED"])
#     - org_unit_code      (allowed_values: ["FIN","IT","HR","OPS","MKT","LOG","R&D","PRO","SAL","ADM"])
#     - responsible_person (no allowed_values, nullable: false)
#     - budget_eur         (no allowed_values, data_type: NUMERIC)
#   Do NOT load from real docs/columns.json — must work standalone.

# mock_anthropic_client() -> MagicMock
#   Returns a MagicMock replacing AsyncAnthropic.
#   .messages.create() is AsyncMock returning a fake Message where:
#     .content[0].text         == '{"intent":"db_query","confidence":0.9,"reason":"test"}'
#     .model                   == "claude-sonnet-4-6"
#     .usage.input_tokens      == 10
#     .usage.output_tokens     == 20

# mock_voyage_client() -> MagicMock
#   Returns a MagicMock replacing voyageai.AsyncClient.
#   .embed() is AsyncMock returning a fake result where:
#     .embeddings == [[0.1] * 1024]

# mock_chroma_collection() -> MagicMock
#   Returns a MagicMock for a ChromaDB collection.
#   .count()  == 5
#   .query()  returns:
#     {
#       "ids":       [["cc_code","status","org_unit_code","responsible_person","budget_eur"]],
#       "documents": [["Cost Center Code: SAP-style code...",
#                      "Status: Operational status...",
#                      "Org Unit Code: Department code...",
#                      "Responsible Person: Full name...",
#                      "Budget EUR: Annual budget..."]],
#       "distances": [[0.05, 0.10, 0.20, 0.35, 0.50]],
#       "metadatas": [[
#         {"column_name":"cc_code","human_label":"Cost Center Code",
#          "data_type":"VARCHAR","nullable":"False","allowed_values":"null"},
#         {"column_name":"status","human_label":"Status",
#          "data_type":"VARCHAR","nullable":"False",
#          "allowed_values":"[\"ACTIVE\",\"INACTIVE\",\"BLOCKED\"]"},
#         {"column_name":"org_unit_code","human_label":"Organisational Unit Code",
#          "data_type":"VARCHAR","nullable":"False",
#          "allowed_values":"[\"FIN\",\"IT\",\"HR\"]"},
#         {"column_name":"responsible_person","human_label":"Responsible Person",
#          "data_type":"VARCHAR","nullable":"False","allowed_values":"null"},
#         {"column_name":"budget_eur","human_label":"Budget (EUR)",
#          "data_type":"NUMERIC","nullable":"False","allowed_values":"null"},
#       ]]
#     }
```

### Tests for Phase 0

**File: `tests/test_phase0_skeleton.py`**

```python
# test_all_required_files_exist
#   Parametrize over every file in the target project structure.
#   assert os.path.exists(filepath) for each.

# test_env_example_has_all_required_keys
#   Parse .env.example with python-dotenv.
#   Required keys: ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS,
#   VOYAGE_API_KEY, VOYAGE_MODEL, DB_HOST, DB_PORT, DB_NAME, DB_USER,
#   DB_PASSWORD, TABLE_NAME, CHROMA_PATH, COLUMN_DOCS_PATH,
#   SIMILARITY_THRESHOLD, MAX_RESULT_ROWS, LOG_PATH.

# test_gitignore_excludes_env_and_secrets
#   Read .gitignore as text.
#   assert ".env" in lines (exact line)
#   assert "chroma_db/" in lines
#   assert "logs/" in lines

# test_pyproject_has_pytest_and_ruff_config
#   import tomllib; parse pyproject.toml.
#   assert "pytest" in doc["tool"]
#   assert "ruff"   in doc["tool"]

# test_conftest_fixtures_are_callable
#   Import conftest; assert each fixture function is callable.

# test_columns_json_has_24_entries
#   Load docs/columns.json.
#   assert len(data["columns"]) == 24

# test_columns_json_every_entry_has_required_fields
#   For each column entry:
#   assert all fields present: column_name, human_label, data_type,
#   nullable, description, example_values

# test_seed_sql_has_create_table_and_inserts
#   Read db/seed.sql as text.
#   assert "CREATE TABLE cost_centers" in content
#   assert content.count("KS-") >= 100
```

**Pass condition:** `uv run pytest tests/test_phase0_skeleton.py -v` — all green.

### ✅ Phase 0 Checklist
- [ ] All skeleton files created
- [ ] `pyproject.toml` sections added
- [ ] `.env.example` with all 16 required keys
- [ ] `.gitignore` excludes `.env`, `chroma_db/`, `logs/`
- [ ] `conftest.py` — all 5 fixtures implemented
- [ ] `tests/test_phase0_skeleton.py` — all tests green
- [ ] `uv run pytest` full suite green

---

## Phase 1 — Configuration

> **Goal:** typed, validated `Settings` class. All runtime values from `.env`. No hardcoded values in `app/`.

### Task 1.1 — `app/config.py`

```python
# from pydantic import SecretStr
# from pydantic_settings import BaseSettings, SettingsConfigDict
# import logging, sys
#
# class Settings(BaseSettings):
#   anthropic_api_key:    SecretStr
#   claude_model:         str = "claude-sonnet-4-6"
#   claude_max_tokens:    int = 4096
#   voyage_api_key:       SecretStr
#   voyage_model:         str = "voyage-3.5"
#   db_host:              str = "localhost"
#   db_port:              int = 5432
#   db_name:              str              # required — "smtdb"
#   db_user:              str              # required
#   db_password:          SecretStr        # required
#   table_name:           str              # required — "cost_centers"
#   chroma_path:          str   = "./chroma_db"
#   column_docs_path:     str   = "./docs/columns.json"
#   similarity_threshold: float = 0.75
#   max_result_rows:      int   = 500
#   log_path:             str   = "./logs/chat.log"
#
#   @property
#   def db_url(self) -> str:
#       return (f"postgresql://{self.db_user}:"
#               f"{self.db_password.get_secret_value()}"
#               f"@{self.db_host}:{self.db_port}/{self.db_name}")
#
#   model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
#
# settings = Settings()
#
# def setup_logging() -> logging.Logger:
#   Creates parent dir of settings.log_path if absent.
#   Clears existing root logger handlers.
#   Adds FileHandler(settings.log_path, encoding="utf-8") + StreamHandler(sys.stdout).
#   Format: "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
#   Level: INFO
#   Returns logging.getLogger("smtdb")
```

### Tests for Phase 1

**File: `tests/test_config.py`**

```python
# test_settings_loads_all_fields(settings_override)
# test_db_url_property(settings_override)
#   assert db_url == "postgresql://test_user:test_password@localhost:5432/smtdb_test"
# test_missing_db_name_raises(monkeypatch)
# test_missing_anthropic_key_raises(monkeypatch)
# test_similarity_threshold_default(monkeypatch)
#   assert == 0.75 when not set
# test_anthropic_key_hidden_in_repr(settings_override)
#   assert "sk-ant-test-key" not in repr(settings_override)
# test_voyage_key_hidden_in_repr(settings_override)
#   assert "pa-test-key" not in repr(settings_override)
# test_db_password_hidden_in_repr(settings_override)
#   assert "test_password" not in repr(settings_override)
# test_setup_logging_creates_log_directory(tmp_path, monkeypatch)
# test_setup_logging_returns_smtdb_logger(tmp_path, monkeypatch)
#   assert logger.name == "smtdb"
```

**Pass condition:** `uv run pytest tests/test_config.py -v` — all green.

### ✅ Phase 1 Checklist
- [ ] All 15 `Settings` fields with correct types
- [ ] `db_url` uses `get_secret_value()` for password
- [ ] All 3 secrets hidden in `repr()`
- [ ] `setup_logging()` creates directory, clears handlers, returns named logger
- [ ] All `tests/test_config.py` tests green
- [ ] `uv run pytest` full suite green

---

## Phase 2 — Graph State

> **Goal:** single typed state object shared by all LangGraph nodes.

### Task 2.1 — `app/state.py`

```python
# class GraphState(TypedDict):
#   messages:             list[BaseMessage]
#   intent:               str | None       # "metadata"|"db_query"|"out_of_scope"
#   retrieved_col_docs:   list[dict]       # top-5 ChromaDB results with scores
#   enhanced_query:       str | None
#   confirmation_message: str | None
#   confirmation_status:  str | None       # "confirmed"|"rejected"|"rephrased"
#   sql:                  str | None       # validated SELECT only
#   db_results:           list[dict] | None
#   final_response:       str | None
#   error:                str | None       # friendly error → triggers END
#   retry_count:          int              # capped at MAX_RETRIES
#
# VALID_INTENTS: frozenset[str] = frozenset({"metadata", "db_query", "out_of_scope"})
# MAX_RETRIES:   int = 3
#
# def initial_state(user_message: str) -> GraphState:
#   Returns GraphState with one HumanMessage; all other fields as None/0/[].
```

### Tests for Phase 2

**File: `tests/test_state.py`**

```python
# test_graph_state_has_exactly_11_fields
# test_valid_intents_is_frozenset_of_three
# test_max_retries_is_three
# test_initial_state_has_one_human_message
# test_initial_state_all_optional_fields_are_none
# test_initial_state_retry_count_is_zero
# test_initial_state_retrieved_col_docs_is_empty_list
```

**Pass condition:** `uv run pytest tests/test_state.py -v` — all green.

### ✅ Phase 2 Checklist
- [ ] `GraphState` TypedDict — exactly 11 fields
- [ ] `VALID_INTENTS` frozenset — exactly 3 members
- [ ] `MAX_RETRIES = 3`
- [ ] `initial_state()` produces correct zero state
- [ ] All `tests/test_state.py` tests green
- [ ] `uv run pytest` full suite green

---

## Phase 3 — LLM & Embedding Clients

> **Goal:** `AsyncAnthropic` singleton and `voyageai.AsyncClient` singleton. No node creates its own client.

### Task 3.1 — `app/tools/llm.py`

```python
# _claude:  AsyncAnthropic       | None = None
# _voyage:  voyageai.AsyncClient | None = None
#
# def get_llm_client() -> AsyncAnthropic
#   Singleton. api_key from settings.anthropic_api_key.get_secret_value()
#
# def get_voyage_client() -> voyageai.AsyncClient
#   Singleton. api_key from settings.voyage_api_key.get_secret_value()
#
# async def chat_complete(system: str, messages: list[dict], **kwargs) -> str
#   model      = settings.claude_model
#   max_tokens = settings.claude_max_tokens
#   system     = system      ← separate Anthropic API param, NOT a message role
#   messages   = messages    ← user/assistant turns only
#   Returns response.content[0].text
#   On any exception → RuntimeError("The AI service is temporarily unavailable. Please try again.")
#   Log raw exception at ERROR level — never include in RuntimeError message.
#
# async def embed(text: str, input_type: str = "query") -> list[float]
#   texts      = [text]
#   model      = settings.voyage_model
#   input_type = input_type   ← "query" at search, "document" at ingestion
#   Returns result.embeddings[0]  (1024 floats)
#   On any exception → RuntimeError("Could not generate embeddings. Please try again.")
#   Log raw exception at ERROR level.
```

### Tests for Phase 3

**File: `tests/test_llm.py`**

```python
# test_get_llm_client_returns_async_anthropic(settings_override)
# test_get_llm_client_is_singleton(settings_override)
# test_get_voyage_client_is_singleton(settings_override)
# test_chat_complete_returns_string(mocker, settings_override)
# test_chat_complete_passes_system_as_separate_param(mocker, settings_override)
#   assert "system" in create_call_kwargs
#   assert not any(m.get("role")=="system" for m in create_call_kwargs["messages"])
# test_chat_complete_uses_correct_model(mocker, settings_override)
# test_chat_complete_raises_friendly_error_on_failure(mocker, settings_override)
#   assert "anthropic" not in str(exc_info.value).lower()
#   assert raw exception text not in error message
# test_embed_returns_1024_floats(mocker, settings_override)
# test_embed_passes_correct_input_type_document(mocker, settings_override)
# test_embed_raises_friendly_error_on_failure(mocker, settings_override)
#   assert "voyage" not in str(exc_info.value).lower()
```

**Pass condition:** `uv run pytest tests/test_llm.py -v` — all green.

### ✅ Phase 3 Checklist
- [ ] `AsyncAnthropic` singleton
- [ ] `voyageai.AsyncClient` singleton
- [ ] `chat_complete` — `system` as separate param (NOT a role), hides raw exceptions
- [ ] `embed` — correct `input_type`, returns 1024 floats, hides raw exceptions
- [ ] All `tests/test_llm.py` tests green
- [ ] `uv run pytest` full suite green

---

## Phase 4 — PostgreSQL Tool

> **Goal:** async query execution against `smtdb.cost_centers`. Only SELECT reaches the database.

### Task 4.1 — `app/tools/postgres.py`

```python
# async def execute_query(sql: str, max_rows: int = None) -> list[dict]
#   1. Strip whitespace.
#   2. If not starts with "SELECT" (case-insensitive):
#      raise ValueError("Only SELECT statements are permitted.")
#   3. If " LIMIT " not in sql (case-insensitive):
#      sql = sql.rstrip(";") + f" LIMIT {max_rows}"
#   4. asyncpg.connect(settings.db_url) → fetch rows
#   5. Convert each row to dict. Serialise:
#      Decimal → str, date → "YYYY-MM-DD", datetime → ISO, UUID → str
#   6. Return list[dict]
#   On asyncpg error:
#     raise RuntimeError("The query could not be completed. Please try rephrasing.")
#     Log raw error at ERROR. Never include in RuntimeError.
#
# async def get_table_columns(table_name: str) -> list[str]
#   Queries information_schema.columns.
#   Returns column_name list in ordinal_position order.
#
# async def validate_schema(table_name: str, doc_column_names: list[str]) -> None
#   Calls get_table_columns. LOG WARNING for mismatches. Never raises.
```

### Tests for Phase 4

**File: `tests/test_postgres.py`**

```python
# All unit tests mock asyncpg. Do not connect to real smtdb.
#
# test_execute_query_rejects_delete
# test_execute_query_rejects_drop
# test_execute_query_rejects_insert
# test_execute_query_rejects_update
# test_execute_query_adds_limit_when_absent(mocker)
# test_execute_query_does_not_double_add_limit(mocker)
# test_execute_query_returns_list_of_dicts(mocker)
# test_execute_query_serialises_decimal(mocker)
#   Decimal("1234.56") → "1234.56" (str)
# test_execute_query_serialises_date(mocker)
#   date(2024,3,15) → "2024-03-15"
# test_execute_query_friendly_error_hides_asyncpg(mocker)
#   assert "asyncpg" not in str(exc_info.value).lower()
#   assert raw postgres error text not in error message
# test_validate_schema_logs_warning_for_missing_column(mocker, caplog)
# test_validate_schema_does_not_raise_on_connection_error(mocker)
#
# Integration (RUN_INTEGRATION=1 only):
# async def test_real_select_from_cost_centers():
#   result = await execute_query("SELECT cc_code FROM cost_centers LIMIT 1")
#   assert result[0]["cc_code"].startswith("KS-")
```

**Pass condition:** `uv run pytest tests/test_postgres.py -v` — all green (integration skipped).

### ✅ Phase 4 Checklist
- [ ] All 4 DML types rejected before any DB connection
- [ ] LIMIT added only when absent, never doubled
- [ ] Decimal and date serialisation correct
- [ ] Friendly RuntimeError hides asyncpg internals
- [ ] `validate_schema` warns but never raises
- [ ] Integration test exists, skipped by default
- [ ] All unit tests green
- [ ] `uv run pytest` full suite green

---

## Phase 5 — ChromaDB Tool

> **Goal:** embed `docs/columns.json` once at startup. Similarity search for `map_columns` and `retrieve_docs`.

### Task 5.1 — `app/tools/chroma.py`

```python
# COLLECTION_NAME = "cost_center_columns"
# _client: chromadb.PersistentClient | None = None
#
# def get_chroma_client() -> chromadb.PersistentClient
#   Singleton. chromadb.PersistentClient(path=settings.chroma_path)
#
# def load_column_docs(path: str = None) -> list[dict]
#   Validates required fields: column_name, human_label, data_type, description.
#   Raises FileNotFoundError or ValueError(f"Column entry missing '{field}': {entry}")
#
# def build_document_text(column: dict) -> str
#   "{human_label}: {description}"
#   + " Examples: {joined}."      if example_values non-empty
#   + " Allowed values: {joined}." if allowed_values non-empty
#
# async def ingest_columns(columns: list[dict], force: bool = False) -> None
#   Creates/gets collection with cosine distance.
#   Skips if count > 0 and not force.
#   Force: delete and recreate.
#   Embeds each column with input_type="document".
#   Stores: id=column_name, document=text, embedding, metadata
#   metadata: column_name, human_label, data_type, nullable(str),
#             allowed_values(JSON string)
#
# async def search_columns(query: str, n_results: int = 5) -> list[dict]
#   Embeds with input_type="query".
#   Raises RuntimeError("Column documentation not found. Run 'make ingest' first.")
#     if collection missing.
#   Returns list[dict]: column_name, human_label, data_type,
#     allowed_values(list), description(str), similarity_score(float, clamped [0,1])
#
# CLI entry point: python -m app.tools.chroma [ingest [--force] | status]
```

### Tests for Phase 5

**File: `tests/test_chroma.py`**

```python
# test_load_column_docs_valid(tmp_path)
# test_load_column_docs_missing_human_label_raises(tmp_path)
# test_load_column_docs_missing_description_raises(tmp_path)
# test_load_column_docs_file_not_found
# test_build_document_text_contains_label_and_description(sample_columns)
# test_build_document_text_includes_allowed_values(sample_columns)
#   "status" column → "ACTIVE" in text, "Allowed values" in text
# test_build_document_text_omits_section_when_empty(sample_columns)
#   "cc_code" column (no allowed_values) → "Allowed values" not in text
# test_ingest_skips_when_collection_exists(mocker, sample_columns)
#   collection.count() == 5, force=False → collection.add NOT called
# test_ingest_force_deletes_and_readds(mocker, sample_columns)
#   force=True → delete_collection called before add
# test_search_returns_correct_shape(mocker, mock_chroma_collection)
#   5 results, each has column_name, human_label, similarity_score in [0,1]
# test_search_raises_helpful_error_when_no_collection(mocker)
#   assert "make ingest" in str(exc_info.value).lower()
# test_similarity_score_conversion()
#   0.0 distance → 1.0 score
#   0.5 distance → 0.5 score
#   1.5 distance → 0.0 score (clamped)
# test_allowed_values_deserialised_as_list(mocker, mock_chroma_collection)
#   status result → allowed_values is list, "ACTIVE" in it
```

**Pass condition:** `uv run pytest tests/test_chroma.py -v` — all green.

### ✅ Phase 5 Checklist
- [ ] `load_column_docs` validates 4 required fields
- [ ] `build_document_text` correct for all combinations
- [ ] `ingest_columns` skip/force logic correct
- [ ] `search_columns` raises helpful error when collection missing
- [ ] `allowed_values` deserialised from JSON string to list
- [ ] Similarity score clamped to [0.0, 1.0]
- [ ] CLI: `ingest`, `ingest --force`, `status`
- [ ] All `tests/test_chroma.py` tests green
- [ ] `uv run pytest` full suite green

---

## Phase 6 — Prompt Templates

> **Goal:** all system prompts and message builders in `app/prompts.py`. All builders return `tuple[str, list[dict]]`.

### Task 6.1 — `app/prompts.py`

```python
# SYSTEM_CLASSIFY_INTENT
#   Three intents with definitions + one example each.
#   Output: ONLY valid JSON {"intent":str,"confidence":float,"reason":str}
#   Must state: if unsure between metadata and db_query, choose db_query.
#
# def build_classify_prompt(user_message: str) -> tuple[str, list[dict]]
#   Returns (SYSTEM_CLASSIFY_INTENT, [{"role":"user","content":user_message}])
#
# SYSTEM_ENHANCE_QUERY
#   Must include: "NEVER invent column names not present in the schema context."
#   Must include: "Use allowed_values strings EXACTLY as listed — case-sensitive."
#   Output: ONLY valid JSON
#     {"enhanced_query":str, "confirmation_message":str,
#      "columns_used":[str], "confidence":float}
#   confirmation_message rules:
#     - Natural language, no SQL
#     - Verbatim allowed_values (e.g. "Status = INACTIVE")
#     - Ends with: "Shall I proceed? (yes / no / rephrase)"
#
# def build_enhance_prompt(user_query: str, column_docs: list[dict]) -> tuple[str, list[dict]]
#   Schema context in user message: column_name, human_label, data_type,
#   allowed_values, description. Omit example_values to save tokens.
#
# SYSTEM_BUILD_SQL
#   Must include: "Return ONLY the raw SQL — no markdown, no explanation"
#   Must include: "Do NOT add a LIMIT clause"
#   Must include: "SELECT only — no INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE"
#   Must include: "Use exact column names and table name from the schema context"
#   Must include: "Use allowed_values strings exactly as listed"
#
# def build_sql_prompt(enhanced_query: str, table_name: str,
#                      column_docs: list[dict]) -> tuple[str, list[dict]]
#
# SYSTEM_HUMANIZE
#   Must include: "Use human_label names in summary, never raw column_name"
#   Must include: "If row_count equals max_result_rows, note results may be truncated"
#   Output: ONLY valid JSON {"summary":str, "column_labels":{column_name:human_label}}
#
# def build_humanize_prompt(sql: str, db_results: list[dict],
#                           column_docs: list[dict], max_rows: int) -> tuple[str, list[dict]]
#   Include row_count + ONLY first 20 rows of db_results.
#
# SYSTEM_ANSWER_FROM_DOCS
#   Must include: "Do not invent or assume information not present in the context."
#   Must include: "If the answer is not in the context, say so."
#
# def build_docs_prompt(user_query: str, column_docs: list[dict]) -> tuple[str, list[dict]]
```

### Tests for Phase 6

**File: `tests/test_prompts.py`**

```python
# test_system_classify_contains_all_three_intents
# test_system_classify_requests_json_with_required_fields
#   "intent","confidence","reason" all in prompt
# test_system_classify_mentions_db_query_as_default
# test_build_classify_prompt_returns_tuple_with_user_message
# test_system_enhance_forbids_invented_columns
# test_system_enhance_requires_verbatim_allowed_values
# test_build_enhance_prompt_includes_status_allowed_values(sample_columns)
#   "ACTIVE" in combined prompt text
# test_system_sql_forbids_limit
# test_system_sql_forbids_markdown
# test_system_sql_forbids_all_dml_keywords
#   insert, update, delete, drop, alter, truncate all in prompt
# test_build_sql_prompt_includes_table_name(sample_columns)
#   "cost_centers" in combined text
# test_build_humanize_prompt_includes_row_count(sample_columns)
#   7 results → "7" in content
# test_build_humanize_prompt_truncates_to_20_rows(sample_columns)
#   100 results → at most 20 appear in prompt
# test_system_answer_from_docs_forbids_hallucination
```

**Pass condition:** `uv run pytest tests/test_prompts.py -v` — all green.

### ✅ Phase 6 Checklist
- [ ] All 5 system prompts implemented
- [ ] All 5 builders return `tuple[str, list[dict]]`
- [ ] SQL prompt: forbids LIMIT + markdown + all DML keywords
- [ ] Enhance prompt: forbids invented columns, requires verbatim `allowed_values`
- [ ] Humanise prompt: truncates to 20 rows, includes row_count
- [ ] Docs prompt: forbids hallucination
- [ ] All `tests/test_prompts.py` tests green
- [ ] `uv run pytest` full suite green

---

## Phase 7 — Graph Nodes

> **Goal:** each node is a standalone async function. Receives `GraphState`, returns partial state `dict`. No node calls another node directly.

> **Raise a clarification request for any node behaviour that is unclear before implementing.**

### Task 7.1 — `app/nodes/classify.py`

```python
# async def classify_intent(state: GraphState) -> dict
#   last_message = state["messages"][-1].content
#   system, messages = build_classify_prompt(last_message)
#   response = await chat_complete(system, messages)
#   Parse JSON. On failure → {"error":"Could not understand your request. Please try again."}
#   If intent not in VALID_INTENTS → log WARNING, default to "db_query"
#   If intent == "out_of_scope" → return:
#     {"intent":"out_of_scope",
#      "final_response":"I can only answer questions about cost center data. "
#                       "Please ask about cost centers, their status, responsible "
#                       "persons, regions, budgets, or departments."}
#   On chat_complete RuntimeError → {"error":"The AI service is temporarily unavailable. Please try again."}
#   Success → {"intent": parsed["intent"]}
```

### Task 7.2 — `app/nodes/retrieve.py`

```python
# async def retrieve_docs(state: GraphState) -> dict
#   docs = await search_columns(state["messages"][-1].content)
#   return {"retrieved_col_docs": docs}
#   On RuntimeError → {"error": "Could not search column documentation. Run 'make ingest' first."}
#
# async def answer_from_docs(state: GraphState) -> dict
#   system, messages = build_docs_prompt(last_message, state["retrieved_col_docs"])
#   response = await chat_complete(system, messages)
#   return {"final_response": response}
#   On RuntimeError → {"error": "..."}
```

### Task 7.3 — `app/nodes/map_columns.py`

```python
# async def map_columns(state: GraphState) -> dict
#   Identical to retrieve_docs. Kept separate for future divergence.
```

### Task 7.4 — `app/nodes/enhance.py`

```python
# async def enhance_query(state: GraphState) -> dict
#   system, messages = build_enhance_prompt(last_message, state["retrieved_col_docs"])
#   response = await chat_complete(system, messages)
#   Parse JSON. On failure → {"error": "Could not interpret your query. Please try rephrasing."}
#   Log WARNING for columns_used entries not found in retrieved_col_docs.
#   return {"enhanced_query": ..., "confirmation_message": ..., "retry_count": current}
```

### Task 7.5 — `app/nodes/confirm.py`

```python
# from langgraph.types import interrupt
#
# CONFIRMED_PHRASES = {"yes","y","correct","ok","okay","confirm","confirmed",
#                      "proceed","looks good","sure","ja","jo"}
# REJECTED_PHRASES  = {"no","n","wrong","incorrect","cancel","stop","nope","nein"}
#
# async def await_confirmation(state: GraphState) -> dict
#   user_response = interrupt({"message": state["confirmation_message"],
#                               "enhanced_query": state["enhanced_query"]})
#   normalised = user_response.strip().lower()
#   status = "confirmed" if normalised in CONFIRMED_PHRASES
#          else "rejected" if normalised in REJECTED_PHRASES
#          else "rephrased"
#   new_retry = state["retry_count"] + (0 if status == "confirmed" else 1)
#   result = {"confirmation_status": status, "retry_count": new_retry}
#   if status == "rephrased":
#       result["messages"] = state["messages"] + [HumanMessage(content=user_response)]
#   return result
```

### Task 7.6 — `app/nodes/sql.py`

```python
# async def build_and_run_sql(state: GraphState) -> dict
#   response = await chat_complete(*build_sql_prompt(
#       state["enhanced_query"], settings.table_name, state["retrieved_col_docs"]))
#
#   # Strip markdown fences
#   sql = response.strip()
#   for fence in ["```sql","```SQL","```"]:
#       if sql.startswith(fence): sql = sql[len(fence):]
#   sql = sql.rstrip("`").strip()
#
#   # Validate
#   try:
#       parsed = sqlglot.parse_one(sql, dialect="postgres")
#   except sqlglot.errors.ParseError:
#       log DEBUG; return {"error":"The generated query was not valid. Please try rephrasing."}
#   if not isinstance(parsed, sqlglot.expressions.Select):
#       return {"error":"Only SELECT queries are supported."}
#
#   # Execute
#   try:
#       results = await execute_query(sql)
#   except (ValueError, RuntimeError) as e:
#       return {"error": str(e)}
#
#   return {"sql": sql, "db_results": results}
#   # sql never stored in state if validation failed
```

### Task 7.7 — `app/nodes/humanize.py`

```python
# async def humanize_response(state: GraphState) -> dict
#   if not state.get("db_results"):
#       return {"final_response":
#           "No results were found for your query. "
#           "This may mean no records match your criteria — "
#           "check filter values are case-sensitive (e.g. INACTIVE not Inactive)."}
#   response = await chat_complete(*build_humanize_prompt(
#       state["sql"], state["db_results"],
#       state["retrieved_col_docs"], settings.max_result_rows))
#   try:
#       summary = json.loads(response)["summary"]
#   except (json.JSONDecodeError, KeyError):
#       summary = response   # fallback
#   return {"final_response": summary}
```

### Tests for Phase 7

**File: `tests/test_nodes.py`**

```python
# All tests mock chat_complete, search_columns, execute_query, interrupt via mocker.

# ── classify_intent ──
# test_classify_returns_db_query(mocker)
# test_classify_falls_back_on_unknown_intent(mocker)
#   unknown intent → result["intent"] == "db_query"
# test_classify_out_of_scope_sets_final_response(mocker)
#   result["intent"]=="out_of_scope", result["final_response"] non-empty
# test_classify_api_error_returns_friendly_error(mocker)
#   RuntimeError from chat_complete → error in result, no raw exception text
# test_classify_malformed_json_returns_error(mocker)

# ── map_columns ──
# test_map_columns_returns_docs(mocker, sample_columns)
# test_map_columns_error_on_search_failure(mocker)

# ── enhance_query ──
# test_enhance_returns_confirmation_with_verbatim_inactive(mocker, sample_columns)
#   confirmation_message contains "INACTIVE"
# test_enhance_malformed_json_returns_error(mocker, sample_columns)

# ── await_confirmation ──
# test_yes_is_confirmed(mocker)
#   retry_count unchanged (stays at 0)
# test_no_is_rejected_and_increments_retry(mocker)
# test_new_query_text_is_rephrased_and_increments_retry(mocker)
# test_rephrased_appends_new_human_message(mocker)
# test_ja_is_confirmed(mocker)
#   German "ja" → confirmed

# ── build_and_run_sql ──
# test_sql_strips_backtick_fences(mocker, sample_columns)
#   "```sql\nSELECT * FROM cost_centers\n```" → sql == "SELECT * FROM cost_centers"
# test_sql_strips_uppercase_fence(mocker, sample_columns)
#   "```SQL\nSELECT 1\n```" → sql == "SELECT 1"
# test_sql_rejects_delete_from_llm(mocker, sample_columns)
#   result.get("sql") is None
# test_sql_returns_results_and_stores_sql(mocker, sample_columns)

# ── humanize_response ──
# test_empty_results_mentions_case_sensitivity(mocker)
#   "INACTIVE" or "case" in final_response
# test_humanize_returns_summary(mocker, sample_columns)
#   "35" in final_response when 35 results given
# test_humanize_fallback_on_malformed_json(mocker, sample_columns)
#   raw chat response used as final_response
```

**Pass condition:** `uv run pytest tests/test_nodes.py -v` — all green.

### ✅ Phase 7 Checklist
- [ ] `classify_intent` — fallback, out_of_scope, friendly errors (no raw text)
- [ ] `retrieve_docs` + `answer_from_docs` — both implemented
- [ ] `map_columns` — separate from retrieve
- [ ] `enhance_query` — logs unmatched columns, JSON fallback
- [ ] `await_confirmation` — yes/no/rephrase, retry logic, messages update, German "ja" works
- [ ] `build_and_run_sql` — markdown strip (both cases), sqlglot check, sql never stored on failure
- [ ] `humanize_response` — empty result mentions case-sensitivity, JSON fallback
- [ ] All `tests/test_nodes.py` tests green
- [ ] `uv run pytest` full suite green

---

## Phase 8 — Graph Assembly

> **Goal:** wire all nodes into `StateGraph` with correct routing, interrupt, and error short-circuit.

> **Raise a clarification request if LangGraph 1.1's `interrupt_before`, `Command`, or `add_conditional_edges` differ from this description.**

### Task 8.1 — `app/graph.py`

```python
# build_graph() -> CompiledGraph
#
# 8 nodes: classify_intent, retrieve_docs, answer_from_docs,
#          map_columns, enhance_query, await_confirmation,
#          build_and_run_sql, humanize_response
#
# Entry: classify_intent
#
# route_intent(state) -> str:
#   error set       → END
#   final_response  → END  (out_of_scope already answered)
#   metadata        → "retrieve_docs"
#   db_query        → "map_columns"
#   else            → END
#
# Metadata path: retrieve_docs → answer_from_docs → END
# DB path:       map_columns → enhance_query → await_confirmation
#
# route_confirmation(state) -> str:
#   error                        → END
#   confirmed                    → "build_and_run_sql"
#   retry_count >= MAX_RETRIES   → END (inject friendly final_response)
#   rephrased                    → "map_columns"  ← re-run retrieval with new query
#   rejected                     → "enhance_query" ← retry with same docs
#
# SQL path: build_and_run_sql → humanize_response → END
#
# Compile:
#   checkpointer = SqliteSaver.from_conn_string(":memory:")
#   graph.compile(checkpointer=checkpointer,
#                 interrupt_before=["await_confirmation"])
#
# get_graph() -> CompiledGraph  (module-level singleton)
```

### Tests for Phase 8

**File: `tests/test_graph.py`**

```python
# test_graph_compiles_without_error
# test_graph_has_all_eight_nodes
# test_get_graph_is_singleton
# test_metadata_path_sets_final_response_no_sql(mocker)
#   result["intent"]=="metadata", final_response set, sql is None
# test_out_of_scope_ends_immediately_no_sql(mocker)
# test_db_query_pauses_at_confirmation(mocker)
#   ← RAISE CLARIFICATION REQUEST if unsure about interrupt exception handling
# test_error_in_classify_short_circuits_to_end(mocker)
#   result["error"] set, sql is None
# test_retry_cap_injects_friendly_final_response(mocker)
#   3 rejections → "trouble understanding" in final_response, sql is None
# test_rephrased_routes_to_map_columns_not_enhance(mocker)
#   rephrased → map_columns called, not enhance_query directly
```

**Pass condition:** `uv run pytest tests/test_graph.py -v` — all green.

### ✅ Phase 8 Checklist
- [ ] All 8 nodes added
- [ ] `route_intent` handles all 5 cases
- [ ] `route_confirmation`: confirmed → sql, rejected → enhance, rephrased → map_columns, retry cap → END
- [ ] Retry cap message contains "trouble understanding"
- [ ] `interrupt_before=["await_confirmation"]`
- [ ] `get_graph()` singleton
- [ ] All `tests/test_graph.py` tests green
- [ ] `uv run pytest` full suite green

---

## Phase 9 — Streamlit UI

> **Goal:** chat interface with interrupt/resume, summary + table, human-readable column headers.

### Task 9.1 — `streamlit_app.py`

```python
# setup_logging() called at module level.
#
# Session state (once per browser session):
#   thread_id:              str  = str(uuid.uuid4())
#   messages:               list = []
#   awaiting_confirmation:  bool = False
#
# Layout: st.title("Cost Center Chat") + st.caption(...)
#
# Render history:
#   for msg in messages:
#       st.chat_message(role) → st.markdown(content)
#       if "dataframe" in msg: st.dataframe(use_container_width=True)
#
# Chat input handler:
#   config = {"configurable":{"thread_id": thread_id}}
#
#   If awaiting_confirmation:
#       result = get_graph().invoke(Command(resume=user_input), config=config)
#       _handle_result(result)
#       awaiting_confirmation = False
#
#   Else (new query):
#       append user message to history; render it
#       try:
#           result = get_graph().invoke(initial_state(user_input), config=config)
#           _handle_result(result)
#       except Exception as e:
#           _handle_interrupt(e)
#           st.rerun()
#
# _handle_interrupt(exc):
#   Extract confirmation_message from interrupt data.
#   Append {"role":"assistant", "content": confirmation + "\n\nReply yes/no/rephrase"}.
#   awaiting_confirmation = True.
#
# _handle_result(result):
#   If error: st.error("Something went wrong. Please try rephrasing.")
#             log raw error at ERROR level; never show raw text.
#   If final_response:
#       msg = {"role":"assistant","content":final_response}
#       if db_results: msg["dataframe"] = _build_dataframe(db_results, col_docs)
#       append to history; render with st.markdown + st.dataframe
#
# _build_dataframe(db_results, col_docs) -> pd.DataFrame:
#   label_map = {c["column_name"]: c["human_label"] for c in col_docs}
#   df = pd.DataFrame(db_results)
#   df.rename(columns=lambda c: label_map.get(c, c), inplace=True)
#   return df
```

### Tests for Phase 9

**File: `tests/test_streamlit_app.py`**

```python
# from streamlit.testing.v1 import AppTest
#
# test_app_loads_without_exception
# test_app_has_title_cost_center_chat
# test_app_initialises_thread_id_as_uuid4
#   len == 36, contains 4 hyphens
# test_app_initialises_awaiting_confirmation_false
# test_app_has_chat_input
# test_build_dataframe_renames_to_human_labels(sample_columns)
#   db_results=[{"status":"ACTIVE","budget_eur":"150000.00"}]
#   df columns: "Status", "Budget (EUR)" — NOT "status", "budget_eur"
# test_build_dataframe_falls_back_for_unmapped_columns(sample_columns)
#   {"unknown_col":"x"} → "unknown_col" in df.columns
```

**Pass condition:** `uv run pytest tests/test_streamlit_app.py -v` — all green.

### ✅ Phase 9 Checklist
- [ ] `thread_id` UUID4 per session
- [ ] Interrupt/resume via `Command(resume=...)`
- [ ] `_handle_result` renders summary + dataframe with human labels
- [ ] `_handle_interrupt` shows confirmation + yes/no/rephrase prompt
- [ ] `st.error()` for errors — raw error never shown
- [ ] `_build_dataframe` renames + falls back
- [ ] `setup_logging()` at module level
- [ ] All `tests/test_streamlit_app.py` tests green
- [ ] `uv run pytest` full suite green

---

## Phase 10 — Integration & End-to-End

> **Goal:** verify full pipeline against real Claude, Voyage AI, and `smtdb`.

### Task 10.1 — Integration tests

**File: `tests/integration/test_e2e.py`**

```python
# Skip unless RUN_INTEGRATION=1. Require valid .env, seeded smtdb, ingested ChromaDB.
#
# test_chroma_collection_has_24_documents
# test_embed_returns_1024_dimensions
# test_chat_complete_responds_to_simple_prompt
# test_full_metadata_query_returns_active_inactive_blocked
#   Intent == metadata, ACTIVE/INACTIVE/BLOCKED in response, sql is None
# test_full_db_query_confirmation_contains_INACTIVE_verbatim
#   interrupt → "INACTIVE" in confirmation message (verbatim, uppercase)
# test_full_db_query_confirmed_produces_valid_select
#   resume "yes" → SELECT in sql, error is None, db_results is list
# test_all_result_rows_have_status_INACTIVE
#   Verifies allowed_values verbatim matching works end-to-end
# test_max_rows_respected
#   len(db_results) <= settings.max_result_rows
# test_non_select_raises_before_reaching_db
#   execute_query("DELETE FROM cost_centers WHERE 1=1") → ValueError
```

### Task 10.2 — `Makefile`

```makefile
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
```

### Task 10.3 — `scripts/check_apis.py`

```python
# Tests both API connections and prints:
# - Claude: response text, model name, token usage
# - Voyage: embedding dimensions, first 3 values
# Exit code 0 on success, 1 on any failure.
```

### ✅ Phase 10 Checklist
- [ ] Integration tests written, skipped without `RUN_INTEGRATION=1`
- [ ] `make test` passes (no real APIs needed)
- [ ] `make ingest` populates ChromaDB with 24 column docs from `docs/columns.json`
- [ ] `make check-apis` verifies Anthropic + Voyage AI
- [ ] `make test-all` passes with real credentials and seeded DB
- [ ] `make run` launches Streamlit without errors
- [ ] Confirmed: "INACTIVE" appears verbatim in confirmation message
- [ ] `uv run pytest` full suite green

---

## Phase 11 — Hardening & Final Checks

> **Goal:** no secrets in code, no raw errors in UI, no lint warnings.

### Task 11.1 — Manual checklist

```
[ ] git check-ignore -v .env         → confirmed ignored
[ ] git status uv.lock               → confirmed tracked
[ ] grep -r "sk-ant\|pa-\|password" app/ → zero matches
[ ] make lint                        → zero warnings
[ ] make typecheck                   → zero errors
[ ] make test                        → zero failures

Smoke tests:
[ ] "What does the Status column mean?"     → metadata, mentions ACTIVE/INACTIVE/BLOCKED
[ ] "Show me all inactive cost centers"     → confirmation contains "INACTIVE" (uppercase)
[ ] Reply "yes"                             → table headers: Status, Cost Center Code etc. (not status, cc_code)
[ ] Reply "no" to a confirmation            → offered to rephrase
[ ] "What is the weather in Munich?"        → canned out_of_scope response, no SQL
[ ] Simulate error                          → st.error() shown, no traceback visible
```

### Tests for Phase 11

**File: `tests/test_hardening.py`**

```python
# test_no_api_keys_in_source_files
#   Walk app/*.py — assert "sk-ant" and "pa-" not in any file content

# test_no_hardcoded_passwords_in_source_files
#   Walk app/*.py — assert no line matches r'password\s*=\s*["\'][^"\']{4,}'

# test_anthropic_key_hidden_in_repr(settings_override)
#   assert "sk-ant-test-key" not in repr(settings_override)

# test_voyage_key_hidden_in_repr(settings_override)
#   assert "pa-test-key" not in repr(settings_override)

# test_db_password_hidden_in_repr(settings_override)
#   assert "test_password" not in repr(settings_override)

# test_chat_complete_error_hides_all_internals(mocker, settings_override)
#   mock to raise Exception("anthropic.APIStatusError: 429 Too Many Requests")
#   with pytest.raises(RuntimeError) as exc_info:
#       await chat_complete("s", [])
#   assert "APIStatusError" not in str(exc_info.value)
#   assert "429"            not in str(exc_info.value)
#   assert "anthropic"      not in str(exc_info.value).lower()

# test_execute_query_error_hides_asyncpg_internals(mocker)
#   mock to raise Exception("asyncpg.exceptions.UndefinedTableError: ...")
#   assert "asyncpg"             not in str(exc_info.value).lower()
#   assert "UndefinedTableError" not in str(exc_info.value)

# test_ruff_check_exits_zero
#   subprocess.run(["uv","run","ruff","check","app/"])
#   assert returncode == 0

# test_env_is_gitignored
#   subprocess.run(["git","check-ignore","-v",".env"])
#   assert returncode == 0
```

**Pass condition:** `uv run pytest tests/test_hardening.py -v` — all green.

### ✅ Phase 11 Checklist
- [ ] No API keys in source files (test verified)
- [ ] No hardcoded passwords (test verified)
- [ ] All 3 secrets hidden in repr (test verified)
- [ ] Anthropic error internals hidden (test verified — checks APIStatusError and 429)
- [ ] asyncpg error internals hidden (test verified)
- [ ] `ruff check` clean (test verified)
- [ ] `.env` gitignored (test verified)
- [ ] Manual smoke tests all passed
- [ ] `uv run pytest` — **zero failures, zero errors, full suite**

---

## Completion Log

*Update after every phase. If a deviation was made without a prior clarification request, explain why.*

| Phase | Status | Completed | Notes / deviations |
|---|---|---|---|
| 0 — Skeleton & test infra | ⬜ pending | | |
| 1 — Configuration | ⬜ pending | | |
| 2 — Graph state | ⬜ pending | | |
| 3 — LLM & embedding clients | ⬜ pending | | |
| 4 — PostgreSQL tool | ⬜ pending | | |
| 5 — ChromaDB tool | ⬜ pending | | |
| 6 — Prompt templates | ⬜ pending | | |
| 7 — Graph nodes | ⬜ pending | | |
| 8 — Graph assembly | ⬜ pending | | |
| 9 — Streamlit UI | ⬜ pending | | |
| 10 — Integration & E2E | ⬜ pending | | |
| 11 — Hardening | ⬜ pending | | |