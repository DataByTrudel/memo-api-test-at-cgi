from fastapi import FastAPI, Body, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any
from llm_utils import prepare_llm_input
from fastapi.middleware.cors import CORSMiddleware
import os

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

app = FastAPI()

allow_origins = [
    "http://localhost:5173",  # local dev
    # future client/tenant host URL placeholder
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Corpus-specific select fields
select_field_lookup = {
    "memos": ["id", "year", "metadata_storage_path", "content"],
    "statutes": ["section_id", "citation", "title", "citation_url", "text_chunks"]
}

# Corpus-specific top-k defaults
default_top_lookup = {
    "memos": 5,
    "statutes": 15
}

def get_search_client(corpus: str) -> SearchClient:
    index_lookup = {
        "memos": os.getenv("SEARCH_INDEX_MEMOS"),
        "statutes": os.getenv("SEARCH_INDEX_CH32")
    }

    index_name = index_lookup.get(corpus, os.getenv("SEARCH_INDEX"))

    print(f"🔍 Using index: {index_name} for corpus: '{corpus}'")

    return SearchClient(
        endpoint=os.getenv("SEARCH_ENDPOINT"),
        index_name=index_name,
        credential=AzureKeyCredential(os.getenv("SEARCH_API_KEY")),
    )

@app.get("/")
def root():
    return {
        "message": "Hello from memo-api-at-cgi",
        "search_endpoint": SEARCH_ENDPOINT,
    }

@app.post("/synthesize")
def synthesize(payload: dict = Body(...)):
    try:
        question = payload.get("question", "")
        ask_response = payload.get("ask_response", {})
        return prepare_llm_input(question, ask_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis prep error: {str(e)}")

@app.post("/synthesize/full")
def synthesize_full(payload: dict = Body(...)):
    try:
        question = payload.get("question", "")
        ask_response = payload.get("ask_response", {})
        llm_input = prepare_llm_input(question, ask_response)
        return mock_gpt_call(llm_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis error: {str(e)}")

from llm_utils import prepare_llm_input, call_gpt

@app.post("/query")
def query(payload: dict = Body(...)):
    try:
        corpus = payload.get("corpus", "memos").lower()
        question = payload.get("question", "")
        year_filter = payload.get("yearFilter", None)
        default_top_lookup = {
            "memos": 5,
            "statutes": 15
        }
        top_k = payload.get("top", default_top_lookup.get(corpus, 5))
        search_client = get_search_client(corpus)
        select_field_lookup = {
            "memos": ["id", "year", "metadata_storage_path", "content"],
            "statutes": ["section_id", "citation", "title", "citation_url", "text_chunks"]
        }
        select_fields = payload.get("select") or select_field_lookup.get(corpus, select_field_lookup["memos"])

        results_iter = search_client.search(
            search_text=question if question.strip() else "*",
            filter=year_filter,
            top=top_k,
            select=",".join(select_fields),
            include_total_count=True,
        )

        results = []

        for r in results_iter:
            doc = r.copy() if isinstance(r, dict) else dict(r)

            if corpus == "statutes":
                combined_text = "\n\n".join(doc.get("text_chunks", []))
                preview = combined_text[:500]
                results.append({
                    "section_id": doc.get("section_id"),
                    "citation": doc.get("citation"),
                    "title": doc.get("title"),
                    "citation_url": doc.get("citation_url"),
                    "content_preview": preview
                })

            else:  # memos
                raw_content = doc.get("content")
                preview = raw_content[:500] if isinstance(raw_content, str) else ""
                results.append({
                    "metadata_storage_path": doc.get("metadata_storage_path"),
                    "content_preview": preview
                })


        ask_response = {
            "results": results
        }

        # Shape → Call GPT
        llm_input = prepare_llm_input(question, ask_response, corpus)
        gpt_response = call_gpt(llm_input, corpus)

        return gpt_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")

# This search route queries the search service directly, skipping over the LLM.
@app.post("/search")
def search(payload: dict = Body(...)):
    try:
        question = payload.get("question", "")
        year_filter = payload.get("yearFilter", None)
        corpus = payload.get("corpus", "memos").lower()

        # Lookup-based configuration
        top_k = payload.get("top", default_top_lookup.get(corpus, 5))
        select_fields = payload.get("select") or select_field_lookup.get(corpus, select_field_lookup["memos"])

        search_client = get_search_client(corpus)

        results_iter = search_client.search(
            search_text=question if question.strip() else "*",
            filter=year_filter,
            top=top_k,
            select=",".join(select_fields),
            include_total_count=True,
        )

        results = []
        for r in results_iter:
            doc = r.copy() if isinstance(r, dict) else dict(r)

            if corpus == "statutes":
                combined_text = "\n\n".join(doc.get("text_chunks", []))
                preview = combined_text[:500]
                results.append({
                    "section_id": doc.get("section_id"),
                    "citation": doc.get("citation"),
                    "title": doc.get("title"),
                    "citation_url": doc.get("citation_url"),
                    "content_preview": preview
                })
            else:
                raw_content = doc.get("content")
                preview = raw_content[:500] if isinstance(raw_content, str) else ""
                results.append({
                    "metadata_storage_path": doc.get("metadata_storage_path"),
                    "content_preview": preview
                })

        return {
            "query": question,
            "corpus": corpus,
            "count": len(results),
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
