
import os
import json
import re
from openai import AzureOpenAI
from corpus_config import corpus_config

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2023-07-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)


def prepare_llm_input(question: str, ask_response: dict, corpus: str) -> dict:
    """Builds a normalized LLM input payload from /query results."""
    config = corpus_config.get(corpus, corpus_config["memos"])
    doc_fields = config.get("document_fields")
    extract_fn = config.get("extract_document_fn")

    documents = []
    for result in ask_response.get("results", []):
        if extract_fn:
            documents.append(extract_fn(result))
        else:
            source = result.get(doc_fields.get("source"), "unknown")

            # Determine which field holds the document text
            content_key = doc_fields.get("content") or doc_fields.get("preview")
            text_content = result.get("content") or result.get(content_key, "")

            url_value = doc_fields.get("url")
            url = (
                url_value
                if isinstance(url_value, str) and url_value.startswith("http")
                else result.get(url_value)
            )

            documents.append({
                "source": source,
                "content": text_content,
                "url": url
            })

    return {
        "question": question,
        "documents": documents
    }


def load_prompt_template(corpus: str) -> str:
    """Loads the correct prompt template for the selected corpus."""
    prompt_file = corpus_config.get(corpus, corpus_config["memos"]).get(
        "prompt_file", "prompt_acheron.txt"
    )
    print(f"📄 Using prompt: {prompt_file} for corpus: '{corpus}'")
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()


def extract_clean_json(response_text: str) -> dict:
    """Removes markdown fences and parses JSON safely."""
    cleaned = re.sub(r"```(json)?", "", response_text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse LLM response as JSON: {str(e)}\nRaw content: {cleaned}"
        )


def call_gpt(llm_input: dict, corpus: str) -> dict:
    """Calls Azure OpenAI and returns parsed JSON or fallback output."""
    prompt_template = load_prompt_template(corpus)

    # Build document block for prompt context
    doc_block = "\n\n---\n\n".join(
        f"DOCUMENT {i + 1}\nSource: {doc.get('source', 'unknown')}\n"
        f"URL: {doc.get('url', 'N/A')}\n\n"
        f"{doc.get('content', '')}\nEND OF DOCUMENT"
        for i, doc in enumerate(llm_input["documents"])
    )

    full_prompt = (
        f"{prompt_template}\n\n"
        f"User question: {llm_input['question']}\n\n"
        f"Retrieved documents:\n{doc_block}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": full_prompt}],
            temperature=0.3,
        )

        raw = response.choices[0].message.content

        # Optional token usage diagnostics
        usage = getattr(response, "usage", None)
        if usage:
            print(
                f"🔢 Token usage — prompt: {usage.prompt_tokens}, "
                f"completion: {usage.completion_tokens}, total: {usage.total_tokens}"
            )

        # Guard against empty responses
        if not raw or not raw.strip():
            return {
                "intent": "interpretive",
                "summary": "[LLM returned empty content]",
                "citations": [],
                "why these": "System fallback: no text returned from LLM.",
            }

        return extract_clean_json(raw)

    except Exception as e:
        return {
            "intent": "interpretive",
            "summary": f"[LLM processing failed: {str(e)}]",
            "citations": [],
            "why these": "System fallback: LLM did not return valid output.",
        }
