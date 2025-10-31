import os

# === Corpus-Specific Document Extractors (for complex cases) ===
def extract_complex_document(result: dict) -> dict:
    # Example transformation for future complex corpus
    return {
        "filename": result.get("complex_id", "unknown") + ".txt",
        "page": result.get("page_number", 1),
        "content": "\n\n".join(result.get("paragraphs", []))
    }

def extract_complex_result(doc: dict) -> dict:
    # Example result shaping for future complex corpus
    preview = " ".join(doc.get("paragraphs", []))[:500]
    return {
        "complex_id": doc.get("complex_id"),
        "content_preview": preview
    }

# === Corpus Configuration Map ===
corpus_config = {
    "memos": {
        "index_name": os.getenv("SEARCH_INDEX_MEMOS"),
        "prompt_file": "prompt_memo.txt",
        "select_fields": ["id", "year", "metadata_storage_path", "content"],
        "default_top": 5,
        "document_fields": {
            "filename": "metadata_storage_path",
            "page": 1,
            "content": "content_preview"
        },
        "result_fields": {
            "filename": "metadata_storage_path",
            "content_preview": "content"
        }
    },
    "statutes": {
        "index_name": os.getenv("SEARCH_INDEX_CH32"),
        "prompt_file": "prompt_ch32.txt",
        "select_fields": ["section_id", "citation", "title", "citation_url", "text_chunks"],
        "default_top": 15,
        "document_fields": {
            "filename": "section_id",
            "page": 1,
            "content": "content_preview"
        },
        "result_fields": {
            "section_id": "section_id",
            "citation": "citation",
            "title": "title",
            "citation_url": "citation_url",
            "content_preview": "text_chunks"
        }
    },
    "complex_demo": {
        "index_name": "placeholder-index",
        "prompt_file": "prompt_complex.txt",
        "select_fields": ["field1", "field2"],
        "default_top": 5,
        "extract_document_fn": extract_complex_document,
        "extract_result_fn": extract_complex_result
    }
}
