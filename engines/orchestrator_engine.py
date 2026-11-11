# F13: Orchestrator Multi-Agent Engine - a third engine behind BaseMenuEngine (F12) that splits
# LangGraphEngine's single pipeline into agents with their own role, responsibilities and goal:
#   1. Orchestrator   - plans which specialists a question needs, then merges their output
#   2. Menu RAG agent - grounded answers from the menu PDFs (F3/F10/F18 retriever)
#   3. MCP Tools agent - an MCP client of api/mcp_server.py (F8): discovers its tools over the
#                        protocol, lets the LLM pick tools + args, and calls them via MCP
#                        (core/mcp_client.py)
#   4. Guard/Verifier - intent gating on the way in (F19), grounding check on the way out
# Specialists 2 and 3 run in parallel (LangGraph fan-out/fan-in). langgraph_engine.py is left
# untouched - this is selectable alongside it via get_engine("orchestrator").
import asyncio
import os
from datetime import date
from typing import Optional, TypedDict

from dotenv import load_dotenv, find_dotenv
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate  # F3.1
from langchain_core.prompts.chat import SystemMessagePromptTemplate, HumanMessagePromptTemplate  # F3.1
from langgraph.graph import StateGraph, END  # F13
from pydantic import BaseModel, Field

from core.domain import domain  # F12
from core.guardrails import classify_intent, is_off_topic, OFF_TOPIC_MESSAGE  # F19
from core.llm import build_llm_and_embeddings  # F2/F12
from core.mcp_client import list_mcp_tools, call_mcp_tools  # F8/F13
from core.memory import wrap_with_memory  # F7
from core.sanitize import INJECTION_DEFENSE_NOTICE, sanitize_content  # F22
from core.vectorstore import get_retriever  # F3/F10/F12/F18/F22
from core.tracing import trace_config  # F9
from engines.base import BaseMenuEngine  # F12

load_dotenv(find_dotenv())

AVAILABLE_CUISINES = domain.COLLECTIONS  # F12: from the active domain pack
MAX_RETRIES = 2  # F13: bounded verify -> re-synthesize loop
MAX_TOOL_CALLS = 4  # F13: cap one planning turn's tool calls, so a confused model can't fan out unbounded sheet reads
GUARDRAILS_ENABLED = os.environ.get("GUARDRAILS_ENABLED", "true").lower() != "false"  # F19


# ---- prompts / structured outputs ----

PLAN_PROMPT = domain.PLAN_PROMPT  # F12

MCP_AGENT_PROMPT = domain.MCP_AGENT_PROMPT  # F12

# F13: the domain's synthesis persona (F3.1 rules widened to live-data results), plus F22's notice
SYNTHESIZE_SYSTEM_PROMPT = domain.SYNTHESIZE_PERSONA + INJECTION_DEFENSE_NOTICE + """
----------------
{context}"""

SYNTHESIZE_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYNTHESIZE_SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template("{question}"),
])


RUN_NAME = "menu-orchestrator"  # F9: LangSmith run name for this engine


class OrchestratorPlan(BaseModel):  # F13: orchestrator's structured routing decision
    use_menu: bool = Field(description="true if the menu PDF specialist is needed")
    use_live_data: bool = Field(description="true if the live-data (MCP tools) specialist is needed")
    reasoning: str = Field(description="one short sentence justifying the plan")


class VerifyDecision(BaseModel):  # F13: guard/verifier's structured output
    grounded: bool
    reasoning: str


class OrchestratorState(TypedDict):  # F13: state threaded through every agent node
    cuisine: str
    question: str
    on_topic: bool
    use_menu: bool
    use_live_data: bool
    documents: list[Document]  # written only by the menu agent
    tool_results: list[str]  # written only by the MCP agent - separate keys so parallel writes never collide
    answer: str
    grounded: bool
    verify_feedback: str
    attempts: int


class OrchestratorEngine(BaseMenuEngine):  # F13: orchestrator + specialists, behind F12's interface
    def __init__(self):
        self.llm, self.embeddings = build_llm_and_embeddings()  # F2/F12
        self.retrievers = {cuisine: get_retriever(cuisine, self.embeddings) for cuisine in AVAILABLE_CUISINES}
        self.mcp_tools = asyncio.run(list_mcp_tools())  # F13: discovered once at startup
        self.mcp_tool_names = {t["function"]["name"] for t in self.mcp_tools}
        self.graph = self._build_graph()  # cuisine travels in state, so one graph serves all three menus
        self.chains_with_memory = {  # F7
            cuisine: wrap_with_memory(lambda q, cuisine=cuisine: self._invoke_graph(cuisine, q))
            for cuisine in AVAILABLE_CUISINES
        }

    # ---- agent 4 (in): guard ----

    def _guard_node(self, state: OrchestratorState) -> dict:  # F19: reject off-topic before any agent spends a call
        if not GUARDRAILS_ENABLED:
            return {"on_topic": True}
        return {"on_topic": not is_off_topic(classify_intent(self.llm, state["question"]))}

    # ---- agent 1: orchestrator ----

    def _plan_node(self, state: OrchestratorState) -> dict:
        plan = self.llm.with_structured_output(OrchestratorPlan).invoke(PLAN_PROMPT.format(question=state["question"]))
        if not plan.use_menu and not plan.use_live_data:  # an on-topic question always gets at least the menu
            return {"use_menu": True, "use_live_data": False}
        return {"use_menu": plan.use_menu, "use_live_data": plan.use_live_data}

    # ---- agent 2: menu RAG ----

    def _menu_agent_node(self, state: OrchestratorState) -> dict:
        if not state["use_menu"]:
            return {"documents": []}
        return {"documents": self.retrievers[state["cuisine"]].invoke(state["question"])}  # F22: already sanitized

    # ---- agent 3: MCP tools ----

    def _mcp_agent_node(self, state: OrchestratorState) -> dict:
        if not state["use_live_data"]:
            return {"tool_results": []}
        today = date.today()
        response = self.llm.bind_tools(self.mcp_tools).invoke([
            SystemMessage(MCP_AGENT_PROMPT.format(weekday=today.strftime("%A"), today=today.isoformat())),
            HumanMessage(state["question"]),
        ])
        # skip hallucinated tool names rather than fail the request; cap the fan-out
        calls = [c for c in response.tool_calls if c["name"] in self.mcp_tool_names][:MAX_TOOL_CALLS]
        results = asyncio.run(call_mcp_tools(calls)) if calls else []
        return {"tool_results": results}

    # ---- agent 1 again: merge specialists' output ----

    def _synthesize_node(self, state: OrchestratorState) -> dict:
        context = self._context(state)
        question = state["question"]
        if state["attempts"] > 0 and state["verify_feedback"]:  # F13: fold verifier feedback into the retry
            question = (
                f"{question}\n\n(Your previous answer was rejected: {state['verify_feedback']}. "
                "Try again, using only the context below.)"
            )
        response = self.llm.invoke(SYNTHESIZE_PROMPT.format_messages(context=context, question=question))
        return {"answer": response.content}

    # ---- agent 4 (out): verifier ----

    def _verify_node(self, state: OrchestratorState) -> dict:
        decision = self.llm.with_structured_output(VerifyDecision).invoke(
            f"Context:\n{self._context(state)}\n\nQuestion: {state['question']}\n\nAnswer: {state['answer']}\n\n"
            "Is the answer fully supported by the context, with nothing invented?"
        )
        return {"grounded": decision.grounded, "verify_feedback": decision.reasoning, "attempts": state["attempts"] + 1}

    def _redirect_node(self, state: OrchestratorState) -> dict:  # F19: off-topic branch
        return {"answer": OFF_TOPIC_MESSAGE, "documents": [], "tool_results": []}

    # ---- edges / wiring ----

    @staticmethod
    def _context(state: OrchestratorState) -> str:
        menu = "\n\n".join(doc.page_content for doc in state["documents"])
        live = "\n\n".join(state["tool_results"])
        return f"Menu excerpts:\n{menu or '(none)'}\n\nLive data:\n{live or '(none)'}"

    def _after_guard(self, state: OrchestratorState) -> str:
        return "on_topic" if state["on_topic"] else "off_topic"

    def _after_verify(self, state: OrchestratorState) -> str:  # F13: bounded retry loop
        if state["grounded"] or state["attempts"] >= MAX_RETRIES:
            return "done"
        return "retry"

    def _build_graph(self):
        graph = StateGraph(OrchestratorState)
        graph.add_node("guard", self._guard_node)
        graph.add_node("plan", self._plan_node)
        graph.add_node("menu_agent", self._menu_agent_node)
        graph.add_node("mcp_agent", self._mcp_agent_node)
        graph.add_node("synthesize", self._synthesize_node)
        graph.add_node("verify", self._verify_node)
        graph.add_node("redirect", self._redirect_node)

        graph.set_entry_point("guard")
        graph.add_conditional_edges("guard", self._after_guard, {"on_topic": "plan", "off_topic": "redirect"})
        graph.add_edge("plan", "menu_agent")  # F13: fan-out - both specialists run in the same step
        graph.add_edge("plan", "mcp_agent")
        graph.add_edge(["menu_agent", "mcp_agent"], "synthesize")  # F13: fan-in - waits for both
        graph.add_edge("synthesize", "verify")
        graph.add_conditional_edges("verify", self._after_verify, {"retry": "synthesize", "done": END})
        graph.add_edge("redirect", END)
        return graph.compile()

    def _invoke_graph(self, cuisine: str, question: str, config: dict | None = None) -> dict:
        result = self.graph.invoke({
            "cuisine": cuisine,
            "question": question,
            "on_topic": True,
            "use_menu": False,
            "use_live_data": False,
            "documents": [],
            "tool_results": [],
            "answer": "",
            "grounded": False,
            "verify_feedback": "",
            "attempts": 0,
        }, config=config)  # F9: run name/tags only on the top-level call; under F7 the memory run carries them
        live_docs = [Document(page_content=r, metadata={"source": "mcp_tools"}) for r in result["tool_results"]]
        return {"result": result["answer"], "source_documents": result["documents"] + live_docs}

    def answer(self, cuisine: str, question: str, session_id: str, use_memory: bool = True) -> dict:
        if cuisine not in self.retrievers:
            raise ValueError(f"Unknown cuisine: {cuisine}")
        if not use_memory:
            return self._invoke_graph(cuisine, question, trace_config(RUN_NAME, cuisine, self.llm))  # F9
        memory_config = trace_config(RUN_NAME, cuisine, self.llm,  # F7 + F9: session id plus run name/tags
                                     {"configurable": {"session_id": f"{cuisine}:{session_id}"}})
        return self.chains_with_memory[cuisine].invoke({"query": question}, config=memory_config)
