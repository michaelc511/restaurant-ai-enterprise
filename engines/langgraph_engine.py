# F13: LangGraph State Machine Engine - upgrades the single fixed retrieve+generate step
# (Modular Engine Strategy Factory (F12)'s PlainRagEngine) into a graph that routes,
# retries, and self-corrects. A second engine behind BaseMenuEngine, selectable the same
# way as plain_rag (engines/base.py's get_engine()). Duplicates rather than extracts
# shared setup from plain_rag_engine.py, same reasoning as F12.1 - core.llm/core.vectorstore
# are shared (F12), the RAG chain/persona and graph wiring below are this engine's own.
from typing import TypedDict

from dotenv import load_dotenv, find_dotenv
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate  # F3.1
from langchain_core.prompts.chat import SystemMessagePromptTemplate, HumanMessagePromptTemplate  # F3.1
from langgraph.graph import StateGraph, END  # F13
from pydantic import BaseModel  # F13: structured route/verify output

from core.llm import build_llm_and_embeddings  # F2/F12
from core.memory import wrap_with_memory  # F7
from core.vectorstore import get_retriever  # F3/F10/F12
from engines.base import BaseMenuEngine  # F12

load_dotenv(find_dotenv())

AVAILABLE_CUISINES = ["sushi", "steak", "italian"]
MAX_RETRIES = 2  # F13: bounded retry loop - self-correct at most this many times, then give up

# F13: same persona/guardrail prompt as plain_rag_engine.py's RAG_SYSTEM_PROMPT (F3.1/F12)
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
----------------
{context}"""

RAG_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(RAG_SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template("{question}"),
])


class RouteDecision(BaseModel):  # F13: routing node's structured output
    on_topic: bool


class VerifyDecision(BaseModel):  # F13: verify node's structured output
    grounded: bool
    reasoning: str


class GraphState(TypedDict):  # F13: state threaded through every node in the graph
    cuisine: str
    question: str
    on_topic: bool
    documents: list[Document]
    answer: str
    grounded: bool
    verify_feedback: str
    attempts: int


class LangGraphEngine(BaseMenuEngine):  # F13: retrieve/generate/verify as a graph, behind F12's interface
    def __init__(self):
        self.llm, self.embeddings = build_llm_and_embeddings()  # F2/F12
        self.retrievers = {}
        self.graphs = {}
        self.chains_with_memory = {}  # F7
        for cuisine in AVAILABLE_CUISINES:
            self.retrievers[cuisine] = get_retriever(cuisine, self.embeddings)  # F3/F10/F12
            self.graphs[cuisine] = self._build_graph()
            self.chains_with_memory[cuisine] = wrap_with_memory(  # F7
                lambda q, cuisine=cuisine: self._invoke_graph(cuisine, q)
            )

    # ---- graph nodes ----

    def _route_node(self, state: GraphState) -> dict:  # F13: principled replacement for F8's detect_ops_intent
        router = self.llm.with_structured_output(RouteDecision)
        decision = router.invoke(
            "Is this question about a restaurant's menu, dishes, hours, or policies? "
            f"Question: {state['question']}"
        )
        return {"on_topic": decision.on_topic}

    def _retrieve_node(self, state: GraphState) -> dict:
        documents = self.retrievers[state["cuisine"]].invoke(state["question"])
        return {"documents": documents}

    def _generate_node(self, state: GraphState) -> dict:
        context = "\n\n".join(doc.page_content for doc in state["documents"])
        question = state["question"]
        if state["attempts"] > 0 and state["verify_feedback"]:  # F13: fold verifier feedback into the retry
            question = (
                f"{question}\n\n(Your previous answer was rejected: {state['verify_feedback']}. "
                "Try again, using only the context below.)"
            )
        messages = RAG_PROMPT.format_messages(context=context, question=question)
        response = self.llm.invoke(messages)
        return {"answer": response.content}

    def _verify_node(self, state: GraphState) -> dict:  # F13: "good enough" vs "try again"
        context = "\n\n".join(doc.page_content for doc in state["documents"])
        verifier = self.llm.with_structured_output(VerifyDecision)
        decision = verifier.invoke(
            f"Context:\n{context}\n\nQuestion: {state['question']}\n\nAnswer: {state['answer']}\n\n"
            "Is the answer fully supported by the context, with nothing invented?"
        )
        return {
            "grounded": decision.grounded,
            "verify_feedback": decision.reasoning,
            "attempts": state["attempts"] + 1,
        }

    def _redirect_node(self, state: GraphState) -> dict:  # F13: off-topic branch, no retrieval/LLM call spent
        return {
            "answer": "I'm not able to help with that - I can answer questions about our menu, hours, and policies.",
            "documents": [],
        }

    # ---- conditional edges ----

    def _after_route(self, state: GraphState) -> str:
        return "on_topic" if state["on_topic"] else "off_topic"

    def _after_verify(self, state: GraphState) -> str:  # F13: bounded retry loop
        if state["grounded"] or state["attempts"] >= MAX_RETRIES:
            return "done"
        return "retry"

    def _build_graph(self):
        graph = StateGraph(GraphState)
        graph.add_node("route", self._route_node)
        graph.add_node("retrieve", self._retrieve_node)
        graph.add_node("generate", self._generate_node)
        graph.add_node("verify", self._verify_node)
        graph.add_node("redirect", self._redirect_node)

        graph.set_entry_point("route")
        graph.add_conditional_edges("route", self._after_route, {"on_topic": "retrieve", "off_topic": "redirect"})
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", "verify")
        graph.add_conditional_edges("verify", self._after_verify, {"retry": "retrieve", "done": END})
        graph.add_edge("redirect", END)
        return graph.compile()

    def _invoke_graph(self, cuisine: str, question: str) -> dict:
        result = self.graphs[cuisine].invoke({
            "cuisine": cuisine,
            "question": question,
            "on_topic": True,
            "documents": [],
            "answer": "",
            "grounded": False,
            "verify_feedback": "",
            "attempts": 0,
        })
        return {"result": result["answer"], "source_documents": result["documents"]}

    def answer(self, cuisine: str, question: str, session_id: str, use_memory: bool = True) -> dict:
        if cuisine not in self.graphs:
            raise ValueError(f"Unknown cuisine: {cuisine}")
        if not use_memory:  # F8: hours questions bypass memory, same reasoning as plain_rag_engine.py
            return self._invoke_graph(cuisine, question)
        memory_config = {"configurable": {"session_id": f"{cuisine}:{session_id}"}}  # F7
        return self.chains_with_memory[cuisine].invoke({"query": question}, config=memory_config)
