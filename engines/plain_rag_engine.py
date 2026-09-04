# F12: the plain-RAG engine - same RetrievalQA logic menu_api.py already runs, reimplemented
# here as its own module behind BaseMenuEngine. menu_api.py is left untouched on purpose.
# Provider selection (core.llm) and the FAISS load-or-build pipeline (core.vectorstore) are
# shared with other engines (F13+) instead of duplicated here; the RAG chain/persona below,
# and menu_api.py's own copies of both, are each engine's/file's own.
from dotenv import load_dotenv, find_dotenv
from langchain_classic.chains import RetrievalQA  # F3
from langchain_core.prompts import ChatPromptTemplate  # F3.1: RAG System Prompt & Persona
from langchain_core.prompts.chat import SystemMessagePromptTemplate, HumanMessagePromptTemplate  # F3.1

from core.llm import build_llm_and_embeddings  # F2/F12
from core.memory import wrap_with_memory  # F7
from core.vectorstore import get_retriever  # F3/F10/F12
from engines.base import BaseMenuEngine  # F12

load_dotenv(find_dotenv())

AVAILABLE_CUISINES = ["sushi", "steak", "italian"]

# F12: same persona/guardrail prompt as menu_api.py's RAG_SYSTEM_PROMPT (F3.1), plus one added
# guideline (retain policy specifics) not yet mirrored back into menu_api.py's copy.
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


class PlainRagEngine(BaseMenuEngine):  # F12: today's RetrievalQA logic, behind the shared interface
    def __init__(self):
        self.llm, self.embeddings = build_llm_and_embeddings()  # F2/F12
        self.qa_chains = {}
        self.qa_chains_with_memory = {}  # F7
        for cuisine in AVAILABLE_CUISINES:
            chain = self._build_qa_chain(cuisine)
            self.qa_chains[cuisine] = chain
            self.qa_chains_with_memory[cuisine] = wrap_with_memory(  # F7
                lambda q, chain=chain: chain.invoke({"query": q})
            )

    def _build_qa_chain(self, cuisine: str):  # F3/F12: same steps as menu_api.py's build_qa_chain()
        retriever = get_retriever(cuisine, self.embeddings)  # F3/F10/F12
        return RetrievalQA.from_chain_type(
            llm=self.llm,
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": RAG_PROMPT},
        )

    def answer(self, cuisine: str, question: str, session_id: str, use_memory: bool = True) -> dict:
        if cuisine not in self.qa_chains:
            raise ValueError(f"Unknown cuisine: {cuisine}")
        if not use_memory:  # F8: hours questions bypass memory, same reasoning as menu_api.py
            return self.qa_chains[cuisine].invoke({"query": question})
        memory_config = {"configurable": {"session_id": f"{cuisine}:{session_id}"}}  # F7
        return self.qa_chains_with_memory[cuisine].invoke({"query": question}, config=memory_config)
