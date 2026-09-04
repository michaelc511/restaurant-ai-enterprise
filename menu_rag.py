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

# Step 3: Set credentials (loaded from shared .env at the repo root, OpenAI or Azure)
load_dotenv(find_dotenv())

if os.environ.get("OPENAI_API_KEY"):
    provider = "openai"
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
elif os.environ.get("AZURE_OPENAI_API_KEY"):
    provider = "azure"
    llm = AzureChatOpenAI(
        azure_endpoint="https://openai-api-management-gw.azure-api.net",
        api_version="2025-01-01-preview",
        deployment_name="gpt-5-mini",
    )
    embeddings = AzureOpenAIEmbeddings(
        azure_endpoint="https://openai-api-management-gw.azure-api.net",
        api_version="2023-05-15",
        deployment="text-embedding-ada-002",
    )
else:
    raise RuntimeError("Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY in the .env file")

print(f"Using provider: {provider}")

# Quick connectivity test — a plain prompt, no FAQ document needed
test_response = llm.invoke("Say 'connection ok' if you can read this.")
print("Test prompt response:", test_response.content)

# Full RAG pipeline — hardcoded to the sushi menu for now

# Load and chunk PDFs using PyPDFLoader and RecursiveCharacterTextSplitter
available_cuisines = ["sushi", "steak", "italian"]
cuisine = input(f"Which menu would you like ({'/'.join(available_cuisines)})? ").strip().lower()
while cuisine not in available_cuisines:
    cuisine = input(f"Please choose one of {'/'.join(available_cuisines)}: ").strip().lower()
menu = f"menus/{cuisine}.pdf"

# 2.1 Load and chunk PDFs using PyPDFLoader 
loader = PyPDFLoader(menu)
documents = loader.load()

# 2.2 Load and chunk PDFs using RecursiveCharacterTextSplitter
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
docs = text_splitter.split_documents(documents)

# 2.3 Generate embeddings (OpenAI or Azure OpenAI, per provider above) and store in FAISS vectorstore
vectorstore = FAISS.from_documents(docs, embeddings)

# 2.4 Run retrieval queries with GPT to fetch contextually relevant chunks
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=vectorstore.as_retriever(),
    return_source_documents=True,
)

# 3.1 Analyze the chunking results: total chunk count and average chunk size
chunk_sizes = [len(doc.page_content) for doc in docs]
print(f"\nTotal chunks: {len(docs)}")
print(f"Average chunk size: {sum(chunk_sizes) / len(chunk_sizes):.0f} characters")

# 3.2Sample query and top matching result
query = "What sushi rolls are on the menu?"
result = qa_chain.invoke({"query": query})

print("\nAnswer:", result["result"])
# print("\n--- Top matching result ---")
# print(result["source_documents"][0].page_content)

# print("\n--- All sources ---")
# for i, doc in enumerate(result["source_documents"], 1):
#     print(f"\nSource {i}:")
#     print(doc.page_content)

# 3.3 Ask the user a question and get the answer from the RAG chain (loop until 'q' to quit)
while True:
    user_query = input(f"\nWhat would you like to know about the {cuisine} menu? (q to quit) ")
    if user_query.strip().lower() == "q":
        break
    user_result = qa_chain.invoke({"query": user_query})
    print("\nAnswer:", user_result["result"])
