# F12: shared LLM/embeddings provider selection - used by every engine (plain_rag today,
# langgraph/crewai/autogen later) instead of each duplicating its own copy. menu_api.py and
# menu_rag.py keep their own inline copies, untouched, on purpose.
import os

from langchain_openai import (  # F2: LLM Selector - OpenAI or Azure
    AzureChatOpenAI,
    AzureOpenAIEmbeddings,
    ChatOpenAI,
    OpenAIEmbeddings,
)


# Other params available on ChatOpenAI/AzureChatOpenAI, for future reference
# (full list: https://platform.openai.com/docs/api-reference/chat/create):
#   max_tokens=500          - hard cap on response length (cost/latency control)
#   top_p=1.0               - nucleus sampling, alternative/complement to temperature
#   frequency_penalty=0.0   - >0 discourages repeating the same tokens
#   presence_penalty=0.0    - >0 encourages introducing new topics/words
#   timeout=30              - seconds before the request gives up
#   max_retries=2           - retries on transient API errors
#   seed=42                 - best-effort reproducibility across calls (not fully guaranteed)
def build_llm_and_embeddings():  # F2/F12: same provider selection every engine needs
    if os.environ.get("OPENAI_API_KEY"):
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)  # 0 = deterministic/focused; default is 1.0
        return llm, OpenAIEmbeddings(model="text-embedding-3-small")
    elif os.environ.get("AZURE_OPENAI_API_KEY"):  # F2
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
        return llm, embeddings
    else:
        raise RuntimeError("Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY in the .env file")
