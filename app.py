from fastapi import FastAPI, Body, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any
from fastapi.middleware.cors import CORSMiddleware
import os
from corpus_config import corpus_config
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from llm_utils import prepare_llm_input, call_gpt
import logging
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger("librarian")

app = FastAPI()

allow_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://[::1]:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_search_client(corpus: str) -> SearchClient:
    index_name = corpus_config.get(corpus, corpus_config["memos"]).get("index_name")
    print(f" Using index: {index_name} for corpus: '{corpus}'")
    return SearchClient(
        endpoint=os.getenv("SEARCH_ENDPOINT"),
        index_name=index_name,
        credential=AzureKeyCredential(os.getenv("SEARCH_API_KEY")),
    )


@app.post("/query")
def query(payload: dict = Body(...)):
    try:
        corpus = payload.get("corpus", "memos").lower()
        config = corpus_config.get(corpus, corpus_config["memos"])

        question = payload.get("question", "")
        year_filter = payload.get("yearFilter", None)
        top_k = payload.get("top", config.get("default_top", 5))
        select_fields = payload.get("select") or config.get("select_fields")

        search_client = get_search_client(corpus)
        results_iter = search_client.search(
            search_text=question if question.strip() else "*",
            filter=year_filter,
            top=top_k,
            select=select_fields,
            include_total_count=True,
        )

        results = []
        extract_result_fn = config.get("extract_result_fn")

        for r in results_iter:
            doc = r.copy() if isinstance(r, dict) else dict(r)

            if extract_result_fn:
                results.append(extract_result_fn(doc))
            else:
                doc_fields = config.get("document_fields")

                shaped = {}
                # Standardized field extraction for LLM input
                for key, value in doc_fields.items():
                    shaped[key] = (
                        value if isinstance(value, str) and value.startswith("http")
                        else doc.get(value)
                    )

                # Clip long content safely for prompt size
                content_val = shaped.get("content", "")

                logger.info(f"{corpus} content sample: {doc.get('text_chunks', [])[:1]}")

                if isinstance(content_val, list):
                    # Join list of chunks (for statutes or any Collection(String) field)
                    shaped["content"] = "\n\n".join([str(x) for x in content_val if x])[:1500]
                elif isinstance(content_val, str):
                    # Simple string fields (memos, etc.)
                    shaped["content"] = content_val[:1500]
                else:
                    # Catch unexpected types (numbers, None, dicts)
                    shaped["content"] = str(content_val)[:1500]

                results.append(shaped)

        ask_response = {"results": results}
        llm_input = prepare_llm_input(question, ask_response, corpus)
        print("🔍 Retrieved documents:", [doc.get("source") for doc in results])
        gpt_response = call_gpt(llm_input, corpus)

        return gpt_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query error: {str(e)}")


@app.post("/search")
def search(payload: dict = Body(...)):
    try:
        corpus = payload.get("corpus", "memos").lower()
        config = corpus_config.get(corpus, corpus_config["memos"])

        question = payload.get("question", "")
        year_filter = payload.get("yearFilter", None)
        top_k = payload.get("top", config.get("default_top", 5))
        select_fields = payload.get("select") or config.get("select_fields")

        search_client = get_search_client(corpus)
        results_iter = search_client.search(
            search_text=question if question.strip() else "*",
            filter=year_filter,
            top=top_k,
            select=" ".join(select_fields),
            include_total_count=True,
        )

        results = []
        extract_result_fn = config.get("extract_result_fn")

        for r in results_iter:
            doc = r.copy() if isinstance(r, dict) else dict(r)

            if extract_result_fn:
                results.append(extract_result_fn(doc))
            else:
                result_fields = config.get("result_fields")

                shaped = {}
                # Standardized field extraction for UI preview
                for key, value in result_fields.items():
                    shaped[key] = (
                        value if isinstance(value, str) and value.startswith("http")
                        else doc.get(value)
                    )

                # Clip long preview text for display
                preview_val = shaped.get("preview", "")
                if isinstance(preview_val, list):
                    shaped["preview"] = "\n\n".join(preview_val)[:500]
                elif isinstance(preview_val, str):
                    shaped["preview"] = preview_val[:500]
                else:
                    shaped["preview"] = str(preview_val)[:500]

                results.append(shaped)

        return {
            "query": question,
            "corpus": corpus,
            "count": len(results),
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
