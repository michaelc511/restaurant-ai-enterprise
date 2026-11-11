# F12: the plain-RAG engine - same RetrievalQA logic menu_api.py already runs, reimplemented
# here as its own module behind BaseMenuEngine. menu_api.py is left untouched on purpose.
# Provider selection (core.llm) and the FAISS load-or-build pipeline (core.vectorstore) are
# shared with other engines (F13+) instead of duplicated here; the RAG chain/persona below,
# and menu_api.py's own copies of both, are each engine's/file's own.
from dotenv import load_dotenv, find_dotenv
from langchain_classic.chains import RetrievalQA  # F3
from langchain_core.prompts import ChatPromptTemplate  # F3.1: RAG System Prompt & Persona
from langchain_core.prompts.chat import SystemMessagePromptTemplate, HumanMessagePromptTemplate  # F3.1

from core.domain import domain  # F12
from core.llm import build_llm_and_embeddings  # F2/F12
from core.memory import wrap_with_memory  # F7
from core.sanitize import INJECTION_DEFENSE_NOTICE  # F22
from core.tracing import trace_config  # F9
from core.vectorstore import get_retriever  # F3/F10/F12/F22
from engines.base import BaseMenuEngine  # F12

load_dotenv(find_dotenv())

AVAILABLE_CUISINES = domain.COLLECTIONS  # F12: from the active domain pack
RUN_NAME = "menu-plain-rag"  # F9: LangSmith run name for this engine

# F3.1/F12: the domain's persona + guidelines, plus F22's notice and the retrieved context
RAG_SYSTEM_PROMPT = domain.RAG_PERSONA + INJECTION_DEFENSE_NOTICE + """
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
            return self.qa_chains[cuisine].invoke({"query": question}, config=trace_config(RUN_NAME, cuisine, self.llm))  # F9
        memory_config = trace_config(RUN_NAME, cuisine, self.llm,  # F7 + F9: session id plus run name/tags
                                     {"configurable": {"session_id": f"{cuisine}:{session_id}"}})
        return self.qa_chains_with_memory[cuisine].invoke({"query": question}, config=memory_config)
