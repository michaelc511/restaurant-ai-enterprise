#!/usr/bin/env python
# coding: utf-8

# # Demo: Building a RAG-powered FAQ Agent with Custom Knowledge

# Step 1: Install required packages -> see requirements.txt

# Step 2: Import dependencies
import os
from dotenv import load_dotenv, find_dotenv
from langchain_openai import (
    AzureChatOpenAI,
    AzureOpenAIEmbeddings,
    ChatOpenAI,
    OpenAIEmbeddings,
)
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts.chat import SystemMessagePromptTemplate, HumanMessagePromptTemplate
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
from core.telemetry import UsageInfo, new_session_totals, track_usage, new_trace_totals, trace_call, log_trace  # F6, F9
from core.memory import wrap_with_memory  # F7
from core.vectorstore import wrap_with_reranking  # F10
from core.database import init_db, log_call, get_session_totals  # F11
from core.sheets import get_daily_specials, get_hours_and_events, detect_ops_intent, resolve_target_days  # F8

# Step 3: Set credentials (loaded from shared .env at the repo root, OpenAI or Azure)
load_dotenv(find_dotenv())

# F2/F3/F6: general debug/testing toggle - set DEBUG_MODE=false in .env to silence
# provider info + connectivity test (F2), chunk stats (F3), and F6/F9/F11's console prints
# (the tracking + DB persistence itself is controlled by METRICS below, not this)
DEBUG_MODE = os.environ.get("DEBUG_MODE", "true").lower() != "false"
METRICS = os.environ.get("METRICS", "true").lower() != "false"  # F6/F9/F11: track + persist regardless of DEBUG_MODE

# Other params available on ChatOpenAI/AzureChatOpenAI, for future reference
# (full list: https://platform.openai.com/docs/api-reference/chat/create):
#   max_tokens=500          - hard cap on response length (cost/latency control)
#   top_p=1.0               - nucleus sampling, alternative/complement to temperature
#   frequency_penalty=0.0   - >0 discourages repeating the same tokens
#   presence_penalty=0.0    - >0 encourages introducing new topics/words
#   timeout=30              - seconds before the request gives up
#   max_retries=2           - retries on transient API errors
#   seed=42                 - best-effort reproducibility across calls (not fully guaranteed)
if os.environ.get("OPENAI_API_KEY"):
    provider = "openai"
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)  # 0 = deterministic/focused; default is 1.0
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
elif os.environ.get("AZURE_OPENAI_API_KEY"):
    provider = "azure"
    llm = AzureChatOpenAI(
        azure_endpoint="https://openai-api-management-gw.azure-api.net",
        api_version="2025-01-01-preview",
        deployment_name="gpt-5-mini",
        temperature=0,  # matches the OpenAI branch above; default is 1.0 if unset
    )
    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint="https://openai-api-management-gw.azure-api.net",
        api_version="2023-05-15",
        deployment="text-embedding-ada-002",
    )
else:
    raise RuntimeError("Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY in the .env file")

if DEBUG_MODE:  # F2: test the LLM - print provider + run a connectivity check
    print(f"Using provider: {provider}")

    # Quick connectivity test — a plain prompt, no FAQ document needed
    test_response = llm.invoke("Say 'connection ok' if you can read this.")
    print("Test prompt response:", test_response.content)

# Full RAG pipeline, wrapped as a reusable function (built once per cuisine, cached by the API below)

# Vectorstore directory
VECTORSTORE_DIR = "vectorstores"

# System prompt for the RAG chain - replaces RetrievalQA's generic default (a bare "use this
# context, say I don't know" instruction) with a consistent restaurant-assistant persona, an
# explicit no-hallucination guardrail, and date-context awareness (matters now that F8 feeds
# this chain resolved dates for hours questions - see with_date_context() below).
RAG_SYSTEM_PROMPT = """You are a friendly, knowledgeable restaurant assistant. Answer guest questions
using ONLY the menu and restaurant information given in the context below - never
invent dishes, prices, ingredients, allergens, or policies that aren't explicitly
there.

Guidelines:
- If the answer isn't in the provided context, say so plainly (e.g. "I don't have
  that information") rather than guessing.
- If the question references a specific date or day (e.g. "today", "Friday",
  "this weekend"), use that to figure out which part of the context applies.
- Keep answers concise and conversational, like speaking to a guest at the
  restaurant - not a bulleted data dump unless they asked for a list.
- Mention prices when referencing specific dishes, if the context gives them.
- When answering about restaurant policies (hours, parking, payment, reservations,
  dress code, corkage, delivery/takeout), state the specific details given in the
  context (fees, time limits, exceptions) rather than a vague paraphrase.
- If asked about something outside the menu or restaurant policies, politely
  redirect back to what you can help with instead of answering off-topic.
----------------
{context}"""

RAG_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(RAG_SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template("{question}"),
])


def build_qa_chain(cuisine: str):
    menu = f"menus/{cuisine}.pdf"
    # Index path for the vectorstore
    index_path = f"{VECTORSTORE_DIR}/{cuisine}"

    # 2.1 Load and chunk PDFs using PyPDFLoader
    loader = PyPDFLoader(menu)
    documents = loader.load()

    # 2.2 Load and chunk PDFs using RecursiveCharacterTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(documents)

    # 2.3 Generate embeddings (OpenAI or Azure OpenAI, per provider above) and store in FAISS vectorstore,
    # or load a previously saved index from disk to avoid re-embedding every run
    if os.path.exists(index_path):
        vectorstore = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    else:
        vectorstore = FAISS.from_documents(docs, embeddings)
        vectorstore.save_local(index_path)

    # 2.4 Run retrieval queries with GPT to fetch contextually relevant chunks
    retriever = wrap_with_reranking(vectorstore.as_retriever())  # F10: cross-encoder re-ranks the retrieved chunks
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True,
        chain_type_kwargs={"prompt": RAG_PROMPT},
    )
    return qa_chain, docs


available_cuisines = ["sushi", "steak", "italian"]

qa_chains = {}
docs_by_cuisine = {}
for c in available_cuisines:
    qa_chains[c], docs_by_cuisine[c] = build_qa_chain(c)

qa_chains_with_memory = {}  # F7
for c in available_cuisines:
    qa_chains_with_memory[c] = wrap_with_memory(lambda q, chain=qa_chains[c]: chain.invoke({"query": q}))

app = FastAPI()

session_usage_totals = new_session_totals()  # F6
session_trace_totals = new_trace_totals()  # F9
init_db()  # F11: create usage_log table if it doesn't exist yet

class AskRequest(BaseModel):
    cuisine: str
    question: str
    session_id: str = "default"  # F7

def format_specials_answer(rows: list[dict]) -> str:  # F8: shared by /ask and the CLI
    if not rows:
        return "There are no active specials for that day."
    lines = [f"[{row['Day']}] {row['Dish Name']} ({row['Price']}) - {row['Description']}" for row in rows]
    return "Specials:\n" + "\n".join(lines)

def format_hours_events(rows: list[dict]) -> str:  # F8: shared by /ask and the CLI - "" when there's nothing to append
    if not rows:
        return ""
    lines = [
        f"{row['Date']} ({row['Day']}) - {row['Event / Holiday']}: {row['Status']} "
        f"{row['Open Time']}-{row['Close Time']}"
        for row in rows
    ]
    return "\n\nGoogle Sheets (F8) - holiday/event schedule for that day:\n" + "\n".join(lines)

def specials_for_question(question: str) -> list[dict]:  # F8: resolves tomorrow/weekend/a weekday/etc., dedupes "All Week" rows
    rows, seen = [], set()
    for d in resolve_target_days(question):
        for row in get_daily_specials(d.strftime("%a")):
            if row["Dish Name"] not in seen:
                seen.add(row["Dish Name"])
                rows.append(row)
    return rows

def hours_for_question(question: str) -> list[dict]:  # F8: resolves tomorrow/weekend/a weekday/etc.
    rows = []
    for d in resolve_target_days(question):
        rows.extend(get_hours_and_events(d.isoformat()))
    return rows

def with_date_context(question: str) -> str:  # F8: shared by /ask and the CLI
    # The RAG chain has no way to resolve "today"/"tomorrow"/"this weekend" on its own -
    # the PDF's hours section is a static weekly schedule, so relative-day phrasing fails
    # to resolve without this, even though the schedule itself is in the retrieved chunk.
    target_days = resolve_target_days(question)
    if len(target_days) == 1:
        d = target_days[0]
        prefix = f"The date being asked about is {d.strftime('%A')}, {d.isoformat()}. "
    else:
        parts = ", ".join(f"{d.strftime('%A')} {d.isoformat()}" for d in target_days)
        prefix = f"The dates being asked about are: {parts}. "
    return prefix + question

@app.post("/ask")
def ask(request: AskRequest):
    cuisine = request.cuisine.strip().lower()
    if cuisine not in qa_chains:
        return {"error": f"Unknown cuisine. Choose one of {available_cuisines}"}

    if request.question.strip().lower() == "tt":  # F11: totals-only shortcut, works regardless of DEBUG_MODE
        return {"cuisine": cuisine, "session_totals": get_session_totals(request.session_id)}

    ops_intent = detect_ops_intent(request.question)  # F8: route obvious specials/hours questions to the live sheet
    if ops_intent == "specials":  # F8: specials only ever live in the sheet, never in the PDF menus - go straight there
        if DEBUG_MODE:
            print("\n[F8] Accessing MCP data source (Google Sheets) - question routed to specials...")
        try:
            answer = format_specials_answer(specials_for_question(request.question))
        except RuntimeError as e:
            return {"error": str(e)}
        return {
            "cuisine": cuisine,
            "answer": answer,
            "top_match": "(F8) Live data from Google Sheets, not a PDF chunk",
        }
    # ops_intent == "hours" is NOT short-circuited here - standard hours might genuinely be in the PDF
    # menu, so the RAG chain gets first crack at it below; only falls back to F8 if RAG comes up empty.

    memory_config = {"configurable": {"session_id": f"{cuisine}:{request.session_id}"}}  # F7
    # F8: give the RAG chain the resolved date(s) for hours questions (today/tomorrow/a
    # weekday/weekend/etc.), so it can resolve against the PDF's static weekly schedule.
    question_for_chain = with_date_context(request.question) if ops_intent == "hours" else request.question
    # F8: hours questions bypass Ephemeral Chat Memory (F7) entirely - RetrievalQA uses the same
    # (memory-contextualized) text for both retrieval and generation, so prior conversation turns
    # about menu items were diluting the embedding and causing the Hours-of-Operation chunk to miss.
    # Hours lookups are standalone factual questions anyway, so this is a safe, contained bypass.

    def invoke_chain():
        if ops_intent == "hours":
            return qa_chains[cuisine].invoke({"query": question_for_chain})
        return qa_chains_with_memory[cuisine].invoke({"query": question_for_chain}, config=memory_config)  # F7

    if METRICS:  # F6/F9: track usage + latency, and persist to F11's DB, regardless of DEBUG_MODE
        with track_usage(session_usage_totals) as cb, trace_call(session_trace_totals) as timer:  # F9: retriever/LLM latency
            result = invoke_chain()
        usage = UsageInfo(
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
            total_tokens=cb.total_tokens,
            total_cost_usd=cb.total_cost,
        )
        log_call(cuisine, request.session_id, request.question, usage)  # F11: persist this call
        durable_totals = get_session_totals(request.session_id)  # F11: durable totals from usage_log, not memory
    else:  # F6: toggle off - skip tracking entirely
        result = invoke_chain()
        usage = None
        durable_totals = None
        timer = None

    answer = result["result"]
    top_match = result["source_documents"][0].page_content
    if ops_intent == "hours":  # F8: always append any live-sheet exceptions/events for the resolved date(s)
        if DEBUG_MODE:
            print("\n[F8] Accessing MCP data source (Google Sheets) - appending any events for the resolved date(s)...")
        try:
            answer += format_hours_events(hours_for_question(request.question))
        except RuntimeError:
            pass  # F8 lookup failed - keep the RAG answer as-is, nothing to append

    response = {
        "cuisine": cuisine,
        "answer": answer,
        "top_match": top_match,
    }
    if usage is not None:  # F6: only include usage in the response when the toggle is on
        response["usage"] = usage
        response["session_totals"] = durable_totals  # F11: durable, SQL-backed totals (not the in-memory F6 dict)
    if timer is not None:  # F9: only include the latency/error breakdown when the toggle is on
        response["trace"] = {
            "retriever_ms": round(timer.retriever_ms, 1),
            "llm_ms": round(timer.llm_ms, 1),
            "total_ms": round(timer.total_ms, 1),
            "errors": session_trace_totals["errors"],
            "calls": session_trace_totals["calls"],
        }
    return response

@app.get("/specials")
def specials(day: Optional[str] = None):  # F8: same core.sheets logic api/mcp_server.py exposes as an MCP tool
    try:
        return {"specials": get_daily_specials(day)}
    except RuntimeError as e:
        return {"error": str(e)}

@app.get("/hours")
def hours(date: Optional[str] = None):  # F8: same core.sheets logic api/mcp_server.py exposes as an MCP tool
    try:
        return {"hours": get_hours_and_events(date)}
    except RuntimeError as e:
        return {"error": str(e)}

# Only runs when this file is executed directly (python3 menu_api.py),
# not when uvicorn imports it to serve the API
if __name__ == "__main__":
    cuisine = input(f"Which menu cuisine would you like ({'/'.join(available_cuisines)})? ").strip().lower()
    while cuisine not in available_cuisines:
        cuisine = input(f"Please choose one of menu {'/'.join(available_cuisines)}: ").strip().lower()

    qa_chain, docs = build_qa_chain(cuisine)
    qa_chain_with_memory = wrap_with_memory(lambda q: qa_chain.invoke({"query": q}))  # F7
    cli_memory_config = {"configurable": {"session_id": f"{cuisine}:cli"}}  # F7

    # 3.1 Analyze the chunking results: total chunk count and average chunk size
    if DEBUG_MODE:  # F3: test the chunking - print chunk count + average chunk size
        chunk_sizes = [len(doc.page_content) for doc in docs]
        print(f"\nTotal chunks: {len(docs)}")
        print(f"Average chunk size: {sum(chunk_sizes) / len(chunk_sizes):.0f} characters")

    # 3.2 Sample query and top matching result
    query = f"What dishes are on the {cuisine} menu?"
    if METRICS:  # F6/F9: track usage + latency, and persist to F11's DB, regardless of DEBUG_MODE
        with track_usage(session_usage_totals) as cb, trace_call(session_trace_totals) as timer:  # F9
            result = qa_chain_with_memory.invoke({"query": query}, config=cli_memory_config)  # F7
        usage = UsageInfo(
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
            total_tokens=cb.total_tokens,
            total_cost_usd=cb.total_cost,
        )
        log_call(cuisine, cli_memory_config["configurable"]["session_id"], query, usage)  # F11: persist this call
        if DEBUG_MODE:  # F6/F9/F11: only print to console when both METRICS and DEBUG_MODE are on
            print(f"\n[F6] Tokens - prompt: {cb.prompt_tokens}, completion: {cb.completion_tokens}, "
                  f"total: {cb.total_tokens} | Cost: ${cb.total_cost:.6f}")
            print(f"[F11] Session Total (DB) - {get_session_totals(cli_memory_config['configurable']['session_id'])}")
            log_trace(timer, session_trace_totals, label="Sample query")  # F9: retriever/LLM latency + error rate
    else:  # F6: toggle off - skip tracking entirely
        result = qa_chain_with_memory.invoke({"query": query}, config=cli_memory_config)  # F7

    print("\nAnswer:", result["result"])
    print("\n--- Top matching result ---")
    print(result["source_documents"][0].page_content)

    # 3.3 Ask the user a question and get the answer from the RAG chain (loop until 'q' to quit)
    while True:
        user_query = input(f"\nWhat would you like to know about the {cuisine} menu? (q to quit) ")
        if user_query.strip().lower() == "q":
            break
        if user_query.strip().lower() == "tt":  # F11: totals-only shortcut, works regardless of DEBUG_MODE
            print(f"\n[F11] Session Total (DB) - "
                  f"{get_session_totals(cli_memory_config['configurable']['session_id'])}")
            continue
        ops_intent = detect_ops_intent(user_query)  # F8: route obvious specials/hours questions to the live sheet
        if ops_intent == "specials":  # F8: specials only ever live in the sheet, never in the PDF menus - go straight there
            if DEBUG_MODE:
                print("\n[F8] Accessing MCP data source (Google Sheets) - question routed to specials...")
            try:
                print(format_specials_answer(specials_for_question(user_query)))
            except RuntimeError as e:
                print(f"[F8] Error: {e}")
            continue
        # ops_intent == "hours" is NOT short-circuited here - standard hours might genuinely be in the PDF
        # menu, so the RAG chain gets first crack at it below; only falls back to F8 if RAG comes up empty.
        # F8: give the RAG chain the resolved date(s) for hours questions (today/tomorrow/a
        # weekday/weekend/etc.), so it can resolve against the PDF's static weekly schedule.
        query_for_chain = with_date_context(user_query) if ops_intent == "hours" else user_query
        # F8: hours questions bypass Ephemeral Chat Memory (F7) entirely - see the matching note in
        # ask() above for why (prior conversation turns were polluting the retrieval embedding).

        def invoke_chain():
            if ops_intent == "hours":
                return qa_chain.invoke({"query": query_for_chain})
            return qa_chain_with_memory.invoke({"query": query_for_chain}, config=cli_memory_config)  # F7

        if METRICS:  # F6/F9: track usage + latency, and persist to F11's DB, regardless of DEBUG_MODE
            with track_usage(session_usage_totals) as cb, trace_call(session_trace_totals) as timer:  # F9
                user_result = invoke_chain()
            usage = UsageInfo(
                prompt_tokens=cb.prompt_tokens,
                completion_tokens=cb.completion_tokens,
                total_tokens=cb.total_tokens,
                total_cost_usd=cb.total_cost,
            )
            log_call(cuisine, cli_memory_config["configurable"]["session_id"], user_query, usage)  # F11: persist this call
            if DEBUG_MODE:  # F6/F9/F11: only print to console when both METRICS and DEBUG_MODE are on
                print(f"\n[F6] Tokens - prompt: {cb.prompt_tokens}, completion: {cb.completion_tokens}, "
                      f"total: {cb.total_tokens} | Cost: ${cb.total_cost:.6f}")
                print(f"[F11] Session Total (DB) - "
                      f"{get_session_totals(cli_memory_config['configurable']['session_id'])}")
                log_trace(timer, session_trace_totals)  # F9: retriever/LLM latency + error rate
        else:  # F6: toggle off - skip tracking entirely
            user_result = invoke_chain()

        answer = user_result["result"]
        if ops_intent == "hours":  # F8: always append any live-sheet exceptions/events for the resolved date(s)
            if DEBUG_MODE:
                print("\n[F8] Accessing MCP data source (Google Sheets) - appending any events for the resolved date(s)...")
            try:
                answer += format_hours_events(hours_for_question(user_query))
            except RuntimeError as e:
                print(f"[F8] Error: {e}")
        print("\nAnswer:", answer)

# F6 - In-Code Token & Cost Accounting: see FEATURES.md for the full writeup
# (what changed, the general-purpose DEBUG_MODE toggle, and how to run/test it).
