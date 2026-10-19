# Menu App — RAG-Powered FAQ Agent

RAG (Retrieval-Augmented Generation) FAQ agent built on LangChain, using OpenAI (or Azure OpenAI as a fallback) for embeddings and chat completion. Answers questions about a restaurant's menu using its PDF menu documents as the source of truth.

## Files

| File | Purpose |
|---|---|
| `prototype/Demo_01_Building_a_RAG_Powered_FAQ_Agent_with_Custom_Knowledge.ipynb` | Original prototype notebook |
| `menu_rag.py` | Standalone script — pick a cuisine, see chunk metrics, ask questions in a terminal loop |
| `menu_rag.ipynb` | Notebook version of `menu_rag.py`, same steps as cells |
| `menu_api.py` | Same RAG pipeline exposed as a FastAPI app (`/ask` endpoint), plus the same terminal mode as `menu_rag.py` when run directly |
| `engine_api.py` | Parallel FastAPI entry point (`/ask`, `/specials`, `/hours`, `/org`, `/items`) that answers through the engine factory instead of an inline chain — `menu_api.py` stays untouched as the baseline — see `features.html` F12 |
| `engines/base.py` | `BaseMenuEngine` interface + `get_engine()` factory (`plain_rag`, `langgraph`) — see `features.html` F12 |
| `engines/plain_rag_engine.py` | Plain RetrievalQA engine — the default (`DEFAULT_ENGINE=plain_rag`) — see `features.html` F12 |
| `engines/langgraph_engine.py` | LangGraph state-machine engine (route → retrieve → generate → verify) — see `features.html` F13 |
| `core/llm.py` | Shared LLM/embeddings provider selection (OpenAI or Azure) used by every engine — see `features.html` F2 and F12 |
| `core/guardrails.py` | Structured intent classifier that rejects off-topic questions before retrieval (`classify_intent`, `is_off_topic`) — see `features.html` F19 |
| `core/sanitize.py` | Delimiter-wraps every retrieved chunk so its content is treated as data, not instructions (`SanitizingRetriever`) — see `features.html` F22 |
| `evaluation/` | RAG evals harness — ground-truth fixtures per cuisine, scored on faithfulness / answer relevancy / context precision (`run_evals.py`) — see `features.html` F17 |
| `.github/workflows/eval_gate.yml` | CI gate — runs `pytest`, then the evals harness — see `features.html` F20 |
| `tests/` | Fully mocked unit tests for the core modules (no API key, no network) — see `features.html` F23 |
| `core/telemetry.py` | Token/cost tracking (`track_usage`, `log_usage`, F6) and step-latency/error-rate tracing (`trace_call`, `log_trace`, F9) — see `features.html` F6 and F9 |
| `core/memory.py` | Ephemeral per-session chat memory (`wrap_with_memory`) — see `features.html` F7 |
| `core/vectorstore.py` | Cross-encoder re-ranking of retrieved chunks (`wrap_with_reranking`) — see `features.html` F10 |
| `core/database.py` | Durable per-call usage log + session totals in SQLite (`log_call`, `get_session_totals`) — see `features.html` F11 |
| `core/sheets.py` | Live daily specials / hours & events, plus the company org directory and items list, read from the `org` Google Sheet (`get_daily_specials`, `get_hours_and_events`, `get_org`, `get_items`) — see `features.html` F8 |
| `api/mcp_server.py` | FastMCP server exposing `core/sheets.py`'s functions as MCP tools for agent runtimes (stdio transport) — see `features.html` F8 |
| `test_mcp_connection.py` | Standalone verification script for `api/mcp_server.py` — spawns it over stdio and calls all four tools |
| `secrets/service_account.json` | Google service account key for `core/sheets.py` (gitignored — not committed) |
| `menus/` | The 3 menu PDFs (`sushi.pdf`, `steak.pdf`, `italian.pdf`) |
| `vectorstores/` | Cached FAISS indexes per cuisine (auto-generated, gitignored — see Notes) |
| `web-demo/gradio_app.py` | Gradio UI, calls `menu_api.py` over HTTP |
| `web-demo/streamlit_app.py` | Streamlit UI, calls `menu_api.py` over HTTP |
| `project-notes.txt` | Project report (intro, implementation, metrics, conclusion) |

## Prerequisites

- Python 3.11+ (see project-notes.txt Conclusion for why — `langchain-classic` requires it)
- A dedicated venv in this folder (not the shared `../venv`, which is on Python 3.9.6)
- Packages in this folder's `requirements.txt`
- An `OPENAI_API_KEY` (or `AZURE_OPENAI_API_KEY`) set in the shared `.env` at the repo root (`serverapp-llm-apis/.env`)

## Setup

Create and activate a Python 3.11 venv (from this folder):

```
/opt/homebrew/bin/python3.11 -m venv venv
source venv/bin/activate
```

Install dependencies:

```
pip install -r requirements.txt
```

Add your key to the shared `.env` at the repo root:

```
OPENAI_API_KEY=your-key-here
```

## Running — terminal mode

```
python3 menu_rag.py
```
or
```
python3 menu_api.py
```
Both prompt you to pick a cuisine, print chunk metrics and a sample query, then loop letting you ask your own questions until you type `q`.

Or open `menu_rag.ipynb` in VS Code / Cursor (install the **Jupyter** and **Python** extensions if the kernel picker doesn't show up), select this folder's `venv` as the kernel, and run all cells.

## Running — FastAPI

Start the API (from this folder, venv activated):

```
uvicorn menu_api:app --reload
```

This builds (or loads from the `vectorstores/` cache) a RAG chain for each cuisine at startup, then serves one endpoint:

- `POST /ask` — body: `{"cuisine": "sushi", "question": "..."}` — returns `{"cuisine", "answer", "top_match"}`

Retrieved chunks are re-ranked by a cross-encoder (`core/vectorstore.py`, F10) before being handed to the LLM, so the most relevant chunk wins even when FAISS's raw similarity search ranks it lower. See `features.html` F10 for the full write-up and how it was tested.

**Test it — command line:**

```
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"cuisine": "sushi", "question": "What rolls are on the menu?"}'
```

**Test it — Postman:**
1. New request → method **POST** → URL `http://127.0.0.1:8000/ask`
2. Body tab → **raw** → type dropdown set to **JSON**
3. Paste:
   ```json
   {
     "cuisine": "sushi",
     "question": "What rolls are on the menu?"
   }
   ```
4. Send

**Test it — auto-generated docs:** open `http://127.0.0.1:8000/docs` in a browser and try `/ask` right from the page.

## Running — engine API (F12)

Same idea as the FastAPI section above, but answers go through `engines/base.py`'s `get_engine()` factory, so you can switch engines without touching the API:

```
uvicorn engine_api:app --reload
```

- `POST /ask` — body: `{"cuisine": "sushi", "question": "...", "session_id": "default", "engine": "langgraph"}` (`session_id` and `engine` are optional; `engine` overrides `DEFAULT_ENGINE` for that one request) — returns `{"cuisine", "answer", "top_match", "engine"}`, plus `usage`/`session_totals` and `trace` when `METRICS` is on
- `GET /specials?day=Mon` — daily specials from the Google Sheet (F8)
- `GET /hours?date=2026-10-12` — hours & events from the Google Sheet (F8)
- `GET /org?type=Department&name=Legal` — company org directory from the sheet's `org` tab (F8)
- `GET /items?category=System%20Status&tenant=London` — company items from the sheet's `items` tab (F8)

`/ask` also answers org questions ("Who heads Legal?", "What are the office hours?") and items questions ("What's the system status in London?") straight from the sheet when a row matches; otherwise the question goes to the engine as usual.

Off-topic questions are rejected up front when `GUARDRAILS_ENABLED` is on (F19).

`python3 engine_api.py` runs the same terminal loop as `menu_api.py`; with `DEBUG_MODE` on it also asks which engine to use.

## Feature toggles

Set in `.env`. Toggles default to on — set to `false` to turn off.

| Variable | Default | Effect |
|---|---|---|
| `DEBUG_MODE` | `true` | Console debug prints; also enables the engine prompt in `engine_api.py`'s terminal mode |
| `METRICS` | `true` | Token/cost (F6), latency tracing (F9), and SQLite usage log (F11) — included in `/ask` responses |
| `GUARDRAILS_ENABLED` | `true` | Off-topic intent gating in `engine_api.py` (F19) |
| `DEFAULT_ENGINE` | `plain_rag` | Engine `engine_api.py` uses — `plain_rag` or `langgraph` (F12/F13) |
| `MEMORY_BACKEND` | `ephemeral` | Chat memory in RAM (F7), or `persistent` for SQLite-backed history that survives a restart (F16) |

## Tests & evals

```
pytest                          # F23: fully mocked unit tests, no API key or network
python -m evaluation.run_evals  # F17: real evals — needs an API key; --cuisine sushi / --engine langgraph
```

CI (`.github/workflows/eval_gate.yml`, F20) runs both.

## Running — web UIs (Gradio / Streamlit)

With `uvicorn menu_api:app --reload` already running in one terminal, open a second terminal (venv activated) and run either:

**Gradio:**
```
python3 web-demo/gradio_app.py
```
Opens automatically at `http://127.0.0.1:7860`.

**Streamlit:**
```
streamlit run web-demo/streamlit_app.py
```
Opens automatically at `http://localhost:8501`.

Both UIs are just front ends — they call `menu_api.py`'s `/ask` endpoint, so the FastAPI server must be running first or requests will fail.

## Notes

- `vectorstores/` is generated automatically the first time each cuisine is embedded, and reused on every run after that to avoid re-embedding (see `build_qa_chain` in `menu_api.py`). It's gitignored — delete it if you want to force a fresh re-embed.
- F10's cross-encoder (`flashrank`, `ms-marco-MiniLM-L-12-v2`) downloads a small model file (~22MB) to a local cache the first time it runs, then loads from cache on every run after that — same pattern as the vectorstores above, just for the re-ranking model instead of the embeddings.
- Currently running on plain OpenAI (not Azure OpenAI) since that's the key set in `.env`. The course rubric specifies Azure OpenAI for embeddings — swap which key is set if that distinction matters for grading.
- `install.sh` (the Homebrew installer script) in this folder is leftover clutter from setup, not part of the project — safe to delete.
