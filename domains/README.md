# Domain packs

Everything domain-specific lives in `domains/<name>/`. The shared code (`core/`, `engines/`,
`engine_api.py`) reads the active pack through `core/domain.py`, picked by the `DOMAIN` env var
(default `restaurant`).

## Packs

- `restaurant` (default): sushi, steak and italian menus, plus specials/hours tools.
- `hr`: Northwind Labs employee handbooks (engineering, sales, operations); shared org/items
  tools only.

## What a pack contains

| Path | Purpose |
|---|---|
| `domain.py` | `NAME`, `COLLECTIONS`, `DOCS_DIR`, `EVALS_DIR`, `COLLECTION_LABEL`, live-data settings (`MCP_SERVER_NAME`, `SPECIALS_TOOL`, `HOURS_TOOL`, `SPECIALS_KEYWORDS`, `HOURS_KEYWORDS`), prompts (`RAG_PERSONA`, `SYNTHESIZE_PERSONA`, `ROUTE_QUESTION`, `PLAN_PROMPT`, `MCP_AGENT_PROMPT`) and F19 intents (`INTENT_LABELS`, `INTENT_DESCRIPTION`, `INTENT_PROMPT`, `OFF_TOPIC_MESSAGE`) |
| `docs/<collection>.pdf` | One source PDF per collection, indexed by `core/vectorstore.py` |
| `evals/<collection>.json` | F17 ground-truth question/answer pairs per collection |
| `sheets.py` | *(optional)* readers for this domain's own Google Sheet tabs, built on `core/sheets.py`'s `_open_tab()` |
| `tools.py` | *(optional)* MCP tools plus `register(mcp)`, which `api/mcp_server.py` calls for the active domain |
| `__init__.py` | Empty; makes the pack importable |

## Adding a domain

1. Copy `domains/restaurant/` to `domains/<name>/`.
2. Replace the PDFs in `docs/` and the fixtures in `evals/`, one per collection.
3. Edit `domain.py`: `NAME`, `COLLECTIONS`, the prompts and the intent labels (keep `off_topic`).
4. Run with `DOMAIN=<name>`. Indexes are built on first use in `vectorstores/<name>/`.
5. `pytest`, then `python -m evaluation.run_evals` with your API key.

Shared by every domain: the `org` and `items` tabs and their `org_directory` / `company_items`
MCP tools (rows carry `App` and `Tenant` columns). A domain without specials or hours data sets
`SPECIALS_TOOL`/`HOURS_TOOL` to `None` and their keyword tuples to `()`; `engine_api.py`'s
`/specials` and `/hours` then return an error.
