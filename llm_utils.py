# llm_utils.py

def prepare_llm_input(question: str, ask_response: dict) -> dict:
    """
    Transforms the /ask API response into a CPF-compatible input format for LLM synthesis.
    """
    documents = []

    for result in ask_response.get("results", []):
        documents.append({
            "filename": result.get("metadata_storage_path", "unknown").split("/")[-1],
            "page": 1,  # Placeholder
            "content": result.get("content_preview", ""),
            "supersedes": False
        })

    return {
        "question": question,
        "documents": documents,
        "instructions": {
            "honor_supersession": True,
            "output_format": "acheron_json"
        }
    }
