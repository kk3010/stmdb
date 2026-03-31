# Speak to My Database — PoC
## Requirements & Architecture Specification
**Version 2.0 — March 2026**

---

## 1. Overview

A natural-language chat interface that allows finance and controlling teams to query cost center data in plain English — without writing SQL or understanding the underlying schema.

The system classifies every user question, either answering it from embedded column documentation or routing it through a human-confirmed SQL pipeline that retrieves data from PostgreSQL and returns a concise summary with a structured table.

| Field | Value |
|---|---|
| Project name | Speak to My Database — PoC |
| Target users | Finance / controlling team |
| Deployment | Local machine (developer laptop) |
| Database | PostgreSQL — `smtdb` |
| Table | `cost_centers` — 24 columns, 150 rows (fake dataset) |
| LLM | Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`) |
| Embeddings | Voyage AI `voyage-3.5` |
| Agent framework | LangGraph 1.1 |
| Vector store | ChromaDB 1.5.5 (local, persistent) |
| UI | Streamlit 1.55.0 |
| Status | PoC — production path defined, not in scope |

---

## 2. Database

### 2.1 Connection

```
Host:     localhost
Port:     5432
Database: smtdb
Table:    cost_centers
Driver:   asyncpg  →  postgresql://user:pass@localhost:5432/smtdb
```

### 2.2 Table Schema — `cost_centers`

24 columns across 6 logical groups. The table is seeded from `docs/seed.sql` (150 rows, deterministic fake data, German naming conventions, SAP-style codes).

#### Identity

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `cc_id` | `SERIAL` | No | Primary key — auto-increment |
| `cc_code` | `VARCHAR(20)` | No | SAP-style unique code: `KS-{ORG}-{NNNN}` e.g. `KS-FIN-0001` |
| `cc_name` | `VARCHAR(120)` | No | Descriptive name e.g. `Finance & Controlling – Bayern 01` |

#### Classification

| Column | Type | Nullable | Allowed values |
|---|---|---|---|
| `cc_type` | `VARCHAR(20)` | No | `COST` \| `PROFIT` \| `INVEST` \| `OVERHEAD` |
| `cc_type_label` | `VARCHAR(40)` | No | `Cost Center` \| `Profit Center` \| `Investment Center` \| `Overhead Center` |
| `status` | `VARCHAR(20)` | No | `ACTIVE` \| `INACTIVE` \| `BLOCKED` |

#### Organisation

| Column | Type | Nullable | Allowed values |
|---|---|---|---|
| `org_unit_code` | `VARCHAR(10)` | No | `FIN` \| `IT` \| `HR` \| `OPS` \| `MKT` \| `LOG` \| `R&D` \| `PRO` \| `SAL` \| `ADM` |
| `org_unit_name` | `VARCHAR(80)` | No | Full department name e.g. `Finance & Controlling` |
| `region_code` | `VARCHAR(10)` | No | ISO 3166-2: `DE-BY` \| `DE-NW` \| `DE-HE` \| `DE-BW` \| `DE-NI` \| `AT-WI` \| `AT-SA` \| `CH-ZH` \| `CH-BE` |
| `region_name` | `VARCHAR(80)` | No | Full name e.g. `Bayern`, `Wien`, `Zürich` |
| `company_code` | `VARCHAR(10)` | No | `1000` \| `2000` \| `3000` |
| `company_name` | `VARCHAR(80)` | No | `Mustermann AG` \| `Beispiel GmbH` \| `Testfirma SE` |

#### Responsibility

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `responsible_person` | `VARCHAR(80)` | No | Full name — German names e.g. `Anna Schmidt` |
| `deputy_person` | `VARCHAR(80)` | Yes | NULL if no deputy assigned |
| `controlling_person` | `VARCHAR(80)` | Yes | NULL if no controlling contact assigned |

#### Validity

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `valid_from` | `DATE` | No | ISO 8601 — always in the past for active CCs |
| `valid_to` | `DATE` | Yes | NULL = open-ended. Inactive/blocked CCs usually have an end date. |

#### Hierarchy

| Column | Type | Nullable | Allowed values |
|---|---|---|---|
| `hierarchy_level` | `VARCHAR(5)` | No | `1` (top) \| `2` (department) \| `3` (team) |
| `parent_cc_code` | `VARCHAR(20)` | Yes | NULL for level-1 CCs; references `cc_code` |

#### Financials

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `budget_eur` | `NUMERIC(15,2)` | No | Annual budget in EUR. Range: 50,000 – 5,000,000 |
| `actual_eur` | `NUMERIC(15,2)` | No | Year-to-date actual spend in EUR. 30–120% of budget. |
| `currency` | `VARCHAR(5)` | No | Always `EUR` |

#### Audit

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `created_at` | `DATE` | No | Record creation date |
| `modified_at` | `DATE` | No | Last modification date |

### 2.3 Dataset Characteristics

| Metric | Value |
|---|---|
| Total rows | 150 |
| ACTIVE | ~103 (69%) |
| INACTIVE | ~35 (23%) |
| BLOCKED | ~12 (8%) |
| Companies | 3 (Mustermann AG, Beispiel GmbH, Testfirma SE) |
| Regions | 9 (5 German, 2 Austrian, 2 Swiss) |
| Org units | 10 |
| CC types | 4 |
| Rows with `valid_to` set | ~30% |
| Rows with `deputy_person` | ~60% |
| Rows with `controlling_person` | ~50% |


## 3. Goals & Non-Goals

### 3.1 Goals

- Allow non-technical finance users to query cost center data in plain English.
- Map user terminology to real PostgreSQL column names via semantic similarity over `docs/columns.json`.
- Always show a human-readable interpretation of the query for confirmation before executing SQL.
- Return results as a brief natural-language summary plus a structured table with human-readable column headers.
- Handle ambiguous queries gracefully — show a best-guess interpretation and ask for correction.
- Keep all data local — no external calls except Anthropic Claude API and Voyage AI API.
- Architect for conversational memory (multi-turn) without enabling it in the PoC.

### 3.2 Non-Goals (PoC scope)

- Multi-user auth or role-based access control.
- Persistent conversation memory across sessions (addable later with one config change).
- Write operations — read-only (`SELECT` only) at all times.
- Multi-table joins or cross-schema queries.
- Production hardening, rate limiting, or cost controls.
- Mobile or web deployment.

---

## 4. Functional Requirements

### 4.1 Intent Classification

Every user message is classified into one of three intents before any further processing:

| Intent | Meaning | Example query |
|---|---|---|
| `metadata` | Question about schema — column meaning, data type, allowed values, business rules | "What does the Status field mean?" |
| `db_query` | Question requiring actual rows or aggregates from `cost_centers` | "Who is responsible for cost center KS-FIN-0003?" |
| `out_of_scope` | Unrelated to cost center data | "What is the weather in Munich?" |

For `out_of_scope`, return a canned response directing the user back to cost center topics. If classification confidence is ambiguous between `metadata` and `db_query`, default to `db_query`.

### 4.2 Metadata Queries

- Retrieve the answer from the pre-embedded `docs/columns.json` documentation via ChromaDB similarity search.
- Return a plain-text explanation — no SQL generated or executed.
- No confirmation step required.

**Example questions this path handles:**

- "What values can the Status column have?" → returns `ACTIVE`, `INACTIVE`, `BLOCKED` from `allowed_values`
- "What does hierarchy level mean?" → returns the description from `columns.json`
- "Which columns can be NULL?" → returns `deputy_person`, `controlling_person`, `valid_to`, `parent_cc_code`

### 4.3 Column Mapping (Schema Grounding)

For `db_query` intent, user terminology is mapped to exact PostgreSQL column names:

- Embed the user query with Voyage AI `voyage-3.5`, `input_type="query"`.
- Retrieve top-5 most similar column documentation chunks from ChromaDB.
- Pass retrieved column metadata to Claude Sonnet 4.6 to produce an enhanced query using real column names and exact `allowed_values` strings.
- If top similarity score < `0.75`, flag as low-confidence and surface the best-guess match to the user before proceeding.

**Critical mapping examples:**

| User says | Maps to column | `allowed_values` used in SQL |
|---|---|---|
| "inactive cost centers" | `status` | `'INACTIVE'` |
| "blocked" | `status` | `'BLOCKED'` |
| "Finance department" | `org_unit_name` or `org_unit_code` | `'Finance & Controlling'` / `'FIN'` |
| "Bayern" or "DE-BY" | `region_name` or `region_code` | `'Bayern'` / `'DE-BY'` |
| "Mustermann AG" | `company_name` or `company_code` | `'Mustermann AG'` / `'1000'` |
| "responsible person" or "who manages" | `responsible_person` | free-text |
| "overhead centers" | `cc_type` | `'OVERHEAD'` |
| "level 2" or "department level" | `hierarchy_level` | `'2'` |
| "over budget" | `actual_eur > budget_eur` | computed expression |

### 4.4 Confirmation Step (Human-in-the-Loop)

Before any SQL is generated or executed, the system suspends and shows the user a plain-language interpretation of their query.

The confirmation message must:

- Use natural language — never show raw SQL to the user.
- State the exact columns that will be filtered and the **verbatim values** from `allowed_values` (e.g. `Status = INACTIVE`, not "inactive status").
- Offer a clear Yes / No / Rephrase path.

If the user rejects or rephrases: the graph loops back to column mapping with the user's correction added to state. Maximum **3 retry attempts** before a graceful failure message.

If the user rephrases: the graph re-runs column mapping against the new query text — it does not reuse the previous column retrieval results.

> **Implementation:** LangGraph 1.1 `interrupt()` in the `await_confirmation` node. Resume via `graph.invoke(Command(resume=user_response), config)`. The graph genuinely suspends — no loop workaround needed.

### 4.5 SQL Generation & Execution

- SQL generated only after explicit user confirmation.
- Only `SELECT` statements permitted — validated before reaching the database.
- `sqlglot 29.0.1` with `dialect="postgres"` parses every generated query. Any non-`SELECT` statement (DDL, DML) is rejected immediately.
- Hard `LIMIT 500` appended to all queries if not already present.
- `asyncpg 0.31.0` executes against `smtdb`.
- On failure: user-friendly error message. Raw PostgreSQL errors never exposed.

**Example queries the pipeline should produce:**

```sql
-- "Show me all inactive cost centers"
SELECT cc_code, cc_name, responsible_person, org_unit_name, region_name
FROM cost_centers
WHERE status = 'INACTIVE'
LIMIT 500;

-- "Which cost centers in Bayern are over budget?"
SELECT cc_code, cc_name, budget_eur, actual_eur, responsible_person
FROM cost_centers
WHERE region_code = 'DE-BY' AND actual_eur > budget_eur
LIMIT 500;

-- "How many cost centers does the IT department have?"
SELECT COUNT(*) AS total_cost_centers
FROM cost_centers
WHERE org_unit_code = 'IT';

-- "Who is responsible for KS-FIN-0003?"
SELECT responsible_person, deputy_person, controlling_person
FROM cost_centers
WHERE cc_code = 'KS-FIN-0003';
```

### 4.6 Response Formatting

Results are presented in two parts:

- **Summary:** 2–4 sentence natural-language summary for a finance audience. Includes record count, key highlights, caveats (truncation, NULL fields).
- **Table:** `st.dataframe()` with column headers from `human_label` in `columns.json` — never raw PostgreSQL column names.

Column header mapping for the fake dataset:

| DB column | Displayed as |
|---|---|
| `cc_code` | Cost Center Code |
| `cc_name` | Cost Center Name |
| `status` | Status |
| `org_unit_name` | Organisational Unit Name |
| `region_name` | Region Name |
| `responsible_person` | Responsible Person |
| `budget_eur` | Budget (EUR) |
| `actual_eur` | Actual Spend (EUR) |

If zero rows returned: say so clearly and suggest checking filter values or spelling (e.g. `INACTIVE` not `Inactive`).

### 4.7 Low-Confidence Fallback

When top ChromaDB similarity score < `0.75`:

- Show the best-guess column with a human-readable confidence indicator: "I think you mean the *Status* column — is that right?"
- Ask the user to confirm or correct.
- Never silently generate SQL from a low-confidence match.

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | End-to-end response (classify → map → confirm → SQL → answer) ≤ 15 seconds. |
| Security | No SQL executed without confirmation. Only `SELECT` permitted. All API keys and DB credentials in `.env` only — never in code. |
| Reliability | All LLM and DB errors caught and shown as friendly messages. App must not crash on any user input. |
| Observability | All node transitions, generated SQL, and row counts logged to `logs/chat.log`. |
| Extensibility | Multi-turn memory addable by swapping `MemorySaver` for `AsyncPostgresSaver` — zero graph changes. |
| Portability | Runnable via `make run` after `.env` setup and `make ingest`. Dependencies pinned in `uv.lock`. |

---

## 6. Tech Stack

| Layer | Technology | Version | Role |
|---|---|---|---|
| Agent framework | LangGraph | **1.1** | StateGraph, `interrupt()`, `Command(resume=...)`, checkpointing |
| LLM | Anthropic Claude Sonnet 4.6 | `claude-sonnet-4-6` | Classification, mapping, SQL generation, humanisation |
| LLM SDK | `anthropic` | **0.86.0** | `AsyncAnthropic` client |
| Embeddings | Voyage AI `voyage-3.5` | current | Column doc ingestion + query-time similarity search |
| Embedding SDK | `voyageai` | current | `voyageai.AsyncClient` |
| Vector store | ChromaDB | **1.5.5** | Local persistent collection `cost_center_columns` |
| DB driver | asyncpg | **0.31.0** | Async queries against `smtdb.cost_centers` |
| SQL validator | sqlglot | **29.0.1** | `parse_one(dialect="postgres")` before every execution |
| Checkpointer | `langgraph-checkpoint-sqlite` | latest | In-memory for PoC; swap to Postgres for production |
| UI | Streamlit | **1.55.0** | `st.chat_message`, `st.dataframe`, `st.session_state` |
| Config | pydantic-settings | **2.13.1** | Typed config from `.env` |
| Python | CPython | **3.12+** | |

---

## 7. Architecture

### 7.1 LLM Client Pattern

The Anthropic Messages API separates system prompts from user messages. All nodes follow this pattern:

```python
# app/tools/llm.py
from anthropic import AsyncAnthropic
import voyageai

async def chat_complete(system: str, messages: list[dict], **kwargs) -> str:
    response = await get_llm_client().messages.create(
        model=settings.claude_model,        # "claude-sonnet-4-6"
        max_tokens=settings.claude_max_tokens,
        system=system,                      # ← separate param, not a role
        messages=messages,                  # ← user/assistant turns only
        **kwargs,
    )
    return response.content[0].text

async def embed(text: str, input_type: str = "query") -> list[float]:
    result = await get_voyage_client().embed(
        texts=[text],
        model=settings.voyage_model,        # "voyage-3.5"
        input_type=input_type,              # "query" at search, "document" at ingestion
    )
    return result.embeddings[0]
```

All prompt builders return `tuple[str, list[dict]]` — `(system_prompt, messages)`:

```python
# app/prompts.py
def build_classify_prompt(user_message: str) -> tuple[str, list[dict]]:
    return (
        SYSTEM_CLASSIFY_INTENT,
        [{"role": "user", "content": user_message}],
    )

# In each node:
system, messages = build_classify_prompt(last_message)
response = await chat_complete(system, messages)
```

### 7.2 GraphState

```python
class GraphState(TypedDict):
    messages:             list[BaseMessage]   # conversation history
    intent:               str | None          # "metadata"|"db_query"|"out_of_scope"
    retrieved_col_docs:   list[dict]          # top-5 ChromaDB results with scores
    enhanced_query:       str | None          # rewritten with real column names
    confirmation_message: str | None          # shown to user before SQL
    confirmation_status:  str | None          # "confirmed"|"rejected"|"rephrased"
    sql:                  str | None          # validated SELECT statement
    db_results:           list[dict] | None   # rows from cost_centers
    final_response:       str | None          # humanised text for Streamlit
    error:                str | None          # friendly error → triggers END
    retry_count:          int                 # max 3

VALID_INTENTS = frozenset({"metadata", "db_query", "out_of_scope"})
MAX_RETRIES = 3
```

### 7.3 Graph Nodes

| Node | Type | What it does |
|---|---|---|
| `classify_intent` | LLM | Classifies into `metadata`, `db_query`, or `out_of_scope` |
| `retrieve_docs` | Tool | ChromaDB search for metadata path |
| `answer_from_docs` | LLM | Answers metadata question from column docs |
| `map_columns` | Tool | Voyage AI embed + ChromaDB top-5 retrieval |
| `enhance_query` | LLM | Rewrites query with real column names and `allowed_values`; produces `confirmation_message` |
| `await_confirmation` | Interrupt | `interrupt()` — graph suspends; resumes on `Command(resume=...)` |
| `build_and_run_sql` | Tool + LLM | Generate SQL → sqlglot validate → asyncpg execute on `smtdb` |
| `humanize_response` | LLM | Formats rows as summary + column label map |

### 7.4 Routing

```
START → classify_intent
          ├─ metadata      → retrieve_docs → answer_from_docs → END
          ├─ out_of_scope  → END (canned response)
          └─ db_query      → map_columns → enhance_query → await_confirmation
                                                │
                                    confirmed ──┤
                                                └→ build_and_run_sql → humanize_response → END
                                    rejected/rephrased (retry < 3) → map_columns (re-retrieval)
                                    retry >= 3 → END (graceful failure)
```

> Rephrased queries route back to `map_columns` — not `enhance_query` — so that column retrieval runs fresh against the user's new query text.

---

## 8. Column Documentation — `docs/columns.json`

The file at `docs/columns.json` is the single source of truth for both ChromaDB ingestion and SQL generation. It documents all 24 columns of `cost_centers`.

### 8.1 Schema

```json
{
  "columns": [
    {
      "column_name":   "status",
      "human_label":   "Status",
      "data_type":     "VARCHAR",
      "nullable":      false,
      "allowed_values": ["ACTIVE", "INACTIVE", "BLOCKED"],
      "description":   "Current operational status of the cost center...",
      "example_values": ["ACTIVE", "INACTIVE"]
    }
  ]
}
```

### 8.2 All 24 Documented Columns

| `column_name` | `human_label` | `allowed_values` |
|---|---|---|
| `cc_id` | Cost Center ID | — |
| `cc_code` | Cost Center Code | — (format: `KS-{ORG}-{NNNN}`) |
| `cc_name` | Cost Center Name | — |
| `cc_type` | Cost Center Type | `COST`, `PROFIT`, `INVEST`, `OVERHEAD` |
| `cc_type_label` | Cost Center Type (Label) | `Cost Center`, `Profit Center`, `Investment Center`, `Overhead Center` |
| `status` | Status | `ACTIVE`, `INACTIVE`, `BLOCKED` |
| `org_unit_code` | Organisational Unit Code | `FIN`, `IT`, `HR`, `OPS`, `MKT`, `LOG`, `R&D`, `PRO`, `SAL`, `ADM` |
| `org_unit_name` | Organisational Unit Name | `Finance & Controlling`, `Information Technology`, … |
| `region_code` | Region Code | `DE-BY`, `DE-NW`, `DE-HE`, `DE-BW`, `DE-NI`, `AT-WI`, `AT-SA`, `CH-ZH`, `CH-BE` |
| `region_name` | Region Name | `Bayern`, `Nordrhein-Westfalen`, `Hessen`, `Baden-Württemberg`, `Niedersachsen`, `Wien`, `Salzburg`, `Zürich`, `Bern` |
| `company_code` | Company Code | `1000`, `2000`, `3000` |
| `company_name` | Company Name | `Mustermann AG`, `Beispiel GmbH`, `Testfirma SE` |
| `responsible_person` | Responsible Person | — (free text, German names) |
| `deputy_person` | Deputy | — (nullable) |
| `controlling_person` | Controlling Person | — (nullable) |
| `valid_from` | Valid From | — (DATE, ISO 8601) |
| `valid_to` | Valid To | — (DATE, nullable) |
| `hierarchy_level` | Hierarchy Level | `1`, `2`, `3` |
| `parent_cc_code` | Parent Cost Center | — (nullable, references `cc_code`) |
| `budget_eur` | Budget (EUR) | — (NUMERIC) |
| `actual_eur` | Actual Spend (EUR) | — (NUMERIC) |
| `currency` | Currency | `EUR` |
| `created_at` | Created On | — (DATE) |
| `modified_at` | Last Modified | — (DATE) |

### 8.3 ChromaDB Ingestion

```bash
make ingest           # first run — embeds all 24 columns with voyage-3.5
make ingest-force     # re-embed from scratch (after editing columns.json)
make status           # show collection document count
```

Each column is embedded as:
```
{human_label}: {description} Examples: {example_values}. Allowed values: {allowed_values}.
```

Embedded with `input_type="document"`. Collection name: `cost_center_columns`. Cosine distance metric. Low confidence threshold: `0.75`.

---

## 9. Edge Cases & Handling

| Scenario | Handling |
|---|---|
| "inactive" → `status = INACTIVE` | `allowed_values` in column doc ensures exact uppercase match |
| "Bayern" or "DE-BY" in same query | Both `region_name` and `region_code` retrieved; LLM selects appropriate column |
| Query involves `actual_eur > budget_eur` | LLM generates computed expression — sqlglot validates it as valid SELECT |
| `deputy_person` is NULL | Humanise response notes the field is not assigned for that record |
| Query maps to no column above 0.75 | Show best-guess match, ask to confirm — never silent |
| User rejects confirmation 3 times | "I'm having trouble understanding. Please try rephrasing from scratch." |
| SQL returns 0 rows | Inform user clearly; suggest checking case sensitivity of filter values |
| SQL returns > 500 rows | Truncate to 500; inform user; suggest adding filters |
| Generated SQL fails sqlglot validation | Do not execute. Log. Return error and offer to rephrase. |
| `smtdb` connection failure | Friendly message. Log raw error. Never expose asyncpg internals. |
| Anthropic API timeout | Retry once. If second attempt fails, graceful error. |
| Voyage AI API error | Graceful error. Log. Never expose raw API error. |

---

## 10. Environment Configuration

### 10.1 `.env`

```dotenv
# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MAX_TOKENS=4096

# Voyage AI (embeddings)
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

### 10.2 `pyproject.toml` dependencies

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
dev = ["pytest", "pytest-asyncio", "ruff", "mypy"]
```

### 10.3 First-run sequence

```bash
uv sync                   # install all dependencies
cp .env.example .env      # fill in your keys and DB credentials
createdb smtdb            # create the local database
psql -U user -d smtdb -f db/seed.sql   # load schema + 150 rows
make check-apis           # verify Anthropic + Voyage AI connections
make ingest               # embed 24 column docs into ChromaDB
make run                  # launch Streamlit at http://localhost:8501
```

---

## 11. Production Path (Post-PoC)

| Capability | Upgrade path |
|---|---|
| Conversational memory | Replace `MemorySaver` with `AsyncPostgresSaver`. Pass `thread_id` per user. No graph changes. |
| Upgrade LLM | Set `CLAUDE_MODEL=claude-opus-4-6` in `.env`. No code changes. |
| Connect to real production DB | Update `DB_*` env vars to point at production `smtdb`. Replace `TABLE_NAME`. Re-run ingestion with real `columns.json`. |
| Multi-user deployment | Add FastAPI backend, JWT auth, per-user `thread_id`s. Swap Streamlit for React. |
| Audit logging | Persist `GraphState` snapshots to a PostgreSQL audit table. |
| Multiple tables | Extend ChromaDB collection with table metadata. Add table-routing node before `map_columns`. |
| Access restrictions | Add column allowlist to `GraphState`. Filter ChromaDB results per user role. |

---

## 12. Open Questions

- **PostgreSQL credentials** — host, port, user, password for `smtdb` on the local instance.
- **Production table name** — the exact table name in the real `smtdb` database (for the eventual production switchover).

---

*Version 2.0 — March 31, 2026. Grounded in the actual `cost_centers` schema (24 columns, 150-row fake dataset) and final tech stack (Claude Sonnet 4.6, Voyage AI voyage-3.5, LangGraph 1.1, ChromaDB 1.5.5).*