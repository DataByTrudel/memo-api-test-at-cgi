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

class AskRequest(BaseModel):
    question: str
    yearFilter: Optional[str] = None     # e.g., "year eq '2023'"
    top: Optional[int] = 5
    select: Optional[List[str]] = None   # e.g., ["id","year","metadata_storage_path","content"]

class AskResult(BaseModel):
    id: Optional[str]
    score: Optional[float]
    year: Optional[str]
    metadata_storage_path: Optional[str]
    content_preview: Optional[str]

class AskResponse(BaseModel):
    query: str
    yearFilter: Optional[str]
    top: int
    count: int
    results: List[AskResult]

@app.get("/")
def root():
    return {
        "message": "Hello from memo-api-at-cgi",
        "search_endpoint": SEARCH_ENDPOINT,
    }

@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest = Body(...)):
    try:
        # Build select list: safe defaults if not provided
        default_select = ["id", "year", "metadata_storage_path", "content"]
        select_fields = payload.select or default_select

        # Run search
        search_client = get_search_client(corpus)
        results_iter = search_client.search(
            search_text=payload.question if payload.question.strip() else "*",
            filter=payload.yearFilter,
            top=payload.top or 5,
            select=",".join(select_fields),
            include_total_count=True,
        )

        results: List[AskResult] = []
        total_count = 0

        for i, r in enumerate(results_iter):
            if i == 0 and hasattr(results_iter, "get_count") and results_iter.get_count() is not None:
                total_count = int(results_iter.get_count())

            doc = r.copy() if isinstance(r, dict) else dict(r)  # ensure dict-like
            # content may be absent in your index; guard and truncate for preview
            raw_content: Any = doc.get("content")
            preview = None
            if isinstance(raw_content, str):
                preview = raw_content[:500]

            results.append(AskResult(
                id=doc.get("id"),
                score=getattr(r, "@search.score", None) or doc.get("@search.score"),
                year=doc.get("year"),
                metadata_storage_path=doc.get("metadata_storage_path"),
                content_preview=preview
            ))

        # If count wasn’t surfaced, derive it
        if total_count == 0:
            total_count = len(results)

        return AskResponse(
            query=payload.question,
            yearFilter=payload.yearFilter,
            top=payload.top or 5,
            count=total_count,
            results=results
        )

    except Exception as e:
        # Return a clean 500 with message (and keep details in platform logs)
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

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
        question = payload.get("question", "")
        year_filter = payload.get("yearFilter", None)
        top_k = payload.get("top", 5)
        corpus = payload.get("corpus", "memos").lower()
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
