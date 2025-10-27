from fastapi import FastAPI, Body, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any
from llm_utils import prepare_llm_input, mock_gpt_call
import os

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

app = FastAPI()

# --- config from env ---
SEARCH_ENDPOINT = os.environ["SEARCH_ENDPOINT"]
SEARCH_API_KEY = os.environ["SEARCH_API_KEY"]
SEARCH_INDEX = os.environ["SEARCH_INDEX"]

# --- construct client once (module import time) ---
search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=SEARCH_INDEX,
    credential=AzureKeyCredential(SEARCH_API_KEY),
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