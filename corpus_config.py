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
        "default_top": 50,
        "policy": "disclose_newer_conflicts",
        "document_fields": {
            "source": "metadata_storage_path",
            "content": "content",
            "url": "https://www.mass.gov/perac-memos",
        },
        "result_fields": {
            "source": "metadata_storage_path",
            "preview": "content",
            "url": "https://www.mass.gov/perac-memos",
        },
    },

    "statutes": {
        "index_name": os.getenv("SEARCH_INDEX_CH32"),
        "prompt_file": "prompt_ch32.txt",
        "select_fields": ["section_id", "citation", "title", "citation_url", "text_chunks"],
        "postprocess_fn": "statutes_prefer_base_sections",
        "default_top": 50,
        "policy": "disclose_newer_conflicts",
        "document_fields": {
            "source": "citation",
            "content": "text_chunks",
            "url": "citation_url",
        },
        "result_fields": {
            "source": "citation",
            "preview": "text_chunks",
            "url": "citation_url",
        },
    },
    "opinions": {
        "index_name": os.getenv("SEARCH_INDEX_OPINIONS", "opinions-index-v4"),
        "prompt_file": "prompt_opinion.txt",
        "select_fields": [
            "opinion_id",
            "title",
            "date",
            "addressee",
            "citation_url",
            "text_chunks"
        ],
        "default_top": 10,
        "policy": "disclose_newer_conflicts"
        "document_fields": {
            "source": "title",
            "content": "text_chunks",
            "url": "citation_url",
        },
        "result_fields": {
            "source": "title",
            "preview": "text_chunks",
            "url": "citation_url",
        },
    }
}

# === Reference Template (Acheron) ===
# This is a placeholder configuration showing the expected shape for new corpus entries.
# Do NOT enable or use this corpus directly. It provides default field naming only.
#
# "acheron": {
#     "index_name": "placeholder-index",
#     "prompt_file": "prompt_acheron.txt",
#     "select_fields": ["id", "title", "url", "content"],
#     "default_top": 10,
#     "policy": "disclose_newer_conflicts"
#     "document_fields": {
#         "source": "title",
#         "content": "content",
#         "url": "url"
#     },
#     "result_fields": {
#         "source": "title",
#         "preview": "content",
#         "url": "url"
#     },
#     "citation_fields": {
#         "source": "title",
#         "url": "url"
#     }
# }
