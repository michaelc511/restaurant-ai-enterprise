#!/usr/bin/env python
# coding: utf-8

# F12: Modular Engine Strategy Factory - the new entry point that answers questions through
# BaseMenuEngine/get_engine() instead of building a RetrievalQA chain inline. menu_api.py is
# left untouched on purpose (still runnable standalone) - this file duplicates its ops-intent
# (F8) helpers and routes rather than importing from it.
import os
from dotenv import load_dotenv, find_dotenv
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel

from core.telemetry import UsageInfo, new_session_totals, track_usage, new_trace_totals, trace_call, log_trace  # F6, F9
from core.database import init_db, log_call, get_session_totals  # F11
from core.sheets import get_daily_specials, get_hours_and_events, detect_ops_intent, resolve_target_days  # F8
from engines.base import get_engine  # F12

load_dotenv(find_dotenv())

DEBUG_MODE = os.environ.get("DEBUG_MODE", "true").lower() != "false"
METRICS = os.environ.get("METRICS", "true").lower() != "false"  # F6/F9/F11: track + persist regardless of DEBUG_MODE; DEBUG_MODE only gates the console prints
DEFAULT_ENGINE = os.environ.get("DEFAULT_ENGINE", "plain_rag")  # F12: which engine answers by default

AVAILABLE_CUISINES = ["sushi", "steak", "italian"]

app = FastAPI()

session_usage_totals = new_session_totals()  # F6
session_trace_totals = new_trace_totals()  # F9
init_db()  # F11: create usage_log table if it doesn't exist yet


class AskRequest(BaseModel):
    cuisine: str
    question: str
    session_id: str = "default"  # F7
    engine: Optional[str] = None  # F12: per-request override of DEFAULT_ENGINE


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
    if cuisine not in AVAILABLE_CUISINES:
        return {"error": f"Unknown cuisine. Choose one of {AVAILABLE_CUISINES}"}

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
    # menu, so the engine gets first crack at it below; only falls back to F8 if it comes up empty.

    # F8: give the engine the resolved date(s) for hours questions (today/tomorrow/a weekday/weekend/etc.),
    # so it can resolve against the PDF's static weekly schedule.
    question_for_engine = with_date_context(request.question) if ops_intent == "hours" else request.question
    use_memory = ops_intent != "hours"  # F8: hours questions bypass Ephemeral Chat Memory (F7), same reasoning as menu_api.py

    engine_name = request.engine or DEFAULT_ENGINE  # F12
    engine = get_engine(engine_name)  # F12

    def invoke_engine():
        return engine.answer(cuisine, question_for_engine, request.session_id, use_memory=use_memory)  # F12

    if METRICS:  # F6/F9: track usage + latency, and persist to F11's DB, regardless of DEBUG_MODE
        with track_usage(session_usage_totals) as cb, trace_call(session_trace_totals) as timer:  # F9
            result = invoke_engine()
        usage = UsageInfo(
            prompt_tokens=cb.prompt_tokens,
            completion_tokens=cb.completion_tokens,
            total_tokens=cb.total_tokens,
            total_cost_usd=cb.total_cost,
        )
        log_call(cuisine, request.session_id, request.question, usage)  # F11: persist this call
        durable_totals = get_session_totals(request.session_id)  # F11: durable totals from usage_log, not memory
    else:  # F6: toggle off - skip tracking entirely
        result = invoke_engine()
        usage = None
        durable_totals = None
        timer = None

    answer = result["result"]
    top_match = result["source_documents"][0].page_content if result["source_documents"] else ""  # F13: LangGraph's off-topic redirect returns no source documents
    if ops_intent == "hours":  # F8: always append any live-sheet exceptions/events for the resolved date(s)
        if DEBUG_MODE:
            print("\n[F8] Accessing MCP data source (Google Sheets) - appending any events for the resolved date(s)...")
        try:
            answer += format_hours_events(hours_for_question(request.question))
        except RuntimeError:
            pass  # F8 lookup failed - keep the engine's answer as-is, nothing to append

    response = {
        "cuisine": cuisine,
        "answer": answer,
        "top_match": top_match,
        "engine": engine_name,  # F12: which engine answered - useful once F13/F14/F15 exist
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


# Only runs when this file is executed directly (python3 engine_api.py),
# not when uvicorn imports it to serve the API
if __name__ == "__main__":
    cuisine = input(f"Which menu cuisine would you like ({'/'.join(AVAILABLE_CUISINES)})? ").strip().lower()
    while cuisine not in AVAILABLE_CUISINES:
        cuisine = input(f"Please choose one of menu {'/'.join(AVAILABLE_CUISINES)}: ").strip().lower()

    cli_session_id = "cli"
    if DEBUG_MODE:  # F13: let a developer override DEFAULT_ENGINE per run, for testing F12's factory
        engine_choice = input(f"\nWhich engine? 1) {DEFAULT_ENGINE} [default, press Enter]  2) LangGraph: ").strip()
        cli_engine_name = "langgraph" if engine_choice == "2" else DEFAULT_ENGINE
        print(f"[DEBUG] DEFAULT_ENGINE is '{DEFAULT_ENGINE}' - using engine: {cli_engine_name}")
    else:
        cli_engine_name = DEFAULT_ENGINE  # F12: no prompt outside DEBUG_MODE, always the .env default
    cli_engine = get_engine(cli_engine_name)  # F12

    while True:
        user_query = input(f"\nWhat would you like to know about the {cuisine} menu? (q to quit) ")
        if user_query.strip().lower() == "q":
            break
        if user_query.strip().lower() == "tt":  # F11: totals-only shortcut, works regardless of DEBUG_MODE
            print(f"\n[F11] Session Total (DB) - {get_session_totals(cli_session_id)}")
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
        # ops_intent == "hours" is NOT short-circuited here - see the matching note in ask() above.
        query_for_engine = with_date_context(user_query) if ops_intent == "hours" else user_query  # F8
        use_memory = ops_intent != "hours"  # F8

        def invoke_engine():
            return cli_engine.answer(cuisine, query_for_engine, cli_session_id, use_memory=use_memory)  # F12

        if METRICS:  # F6/F9: track usage + latency, and persist to F11's DB, regardless of DEBUG_MODE
            with track_usage(session_usage_totals) as cb, trace_call(session_trace_totals) as timer:  # F9
                user_result = invoke_engine()
            usage = UsageInfo(
                prompt_tokens=cb.prompt_tokens,
                completion_tokens=cb.completion_tokens,
                total_tokens=cb.total_tokens,
                total_cost_usd=cb.total_cost,
            )
            log_call(cuisine, cli_session_id, user_query, usage)  # F11: persist this call
            if DEBUG_MODE:  # F6/F9/F11: only print to console when both METRICS and DEBUG_MODE are on
                print(f"\n[F6] Tokens - prompt: {cb.prompt_tokens}, completion: {cb.completion_tokens}, "
                      f"total: {cb.total_tokens} | Cost: ${cb.total_cost:.6f}")
                print(f"[F11] Session Total (DB) - {get_session_totals(cli_session_id)}")
                log_trace(timer, session_trace_totals)  # F9: retriever/LLM latency + error rate
        else:  # F6: toggle off - skip tracking entirely
            user_result = invoke_engine()

        answer = user_result["result"]
        if ops_intent == "hours":  # F8: always append any live-sheet exceptions/events for the resolved date(s)
            if DEBUG_MODE:
                print("\n[F8] Accessing MCP data source (Google Sheets) - appending any events for the resolved date(s)...")
            try:
                answer += format_hours_events(hours_for_question(user_query))
            except RuntimeError as e:
                print(f"[F8] Error: {e}")
        print("\nAnswer:", answer)

# F12 - Modular Engine Strategy Factory: see FEATURES.md for the full writeup.
