# llm_utils.py
import openai
import os
import json
import re
from openai import AzureOpenAI
from corpus_config import corpus_config

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2023-07-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def prepare_llm_input(question: str, ask_response: dict, corpus: str) -> dict:
    config = corpus_config.get(corpus, corpus_config["memos"])
    doc_fields = config.get("document_fields")
    extract_fn = config.get("extract_document_fn")

    documents = []
    for result in ask_response.get("results", []):
        if extract_fn:
            documents.append(extract_fn(result))
        else:
            documents.append({
                "filename": result.get(doc_fields["filename"], "unknown"),
                "page": doc_fields["page"],
                "content": result.get(doc_fields["content"], "")
            })

    return {
        "question": question,
        "documents": documents
    }

def load_prompt_template(corpus: str) -> str:
    prompt_file = corpus_config.get(corpus, corpus_config["memos"]).get("prompt_file", "prompt_acheron.txt")
    print(f"\U0001F4C4 Using prompt: {prompt_file} for corpus: '{corpus}'")
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()

def extract_clean_json(response_text: str) -> dict:
    cleaned = re.sub(r"```(json)?", "", response_text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}\nRaw content: {cleaned}")

def call_gpt(llm_input: dict, corpus: str) -> dict:
    prompt_template = load_prompt_template(corpus)

    doc_block = "\n\n".join(
        f"{doc['filename']} (p. {doc['page']}):\n{doc['content']}"
        for doc in llm_input["documents"]
    )

    full_prompt = f"{prompt_template}\n\nUser question: {llm_input['question']}\n\nRetrieved documents:\n{doc_block}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": full_prompt}],
            temperature=0.3
        )
        raw = response.choices[0].message.content
        return extract_clean_json(raw)

    except Exception as e:
        return {
            "intent": "interpretive",
            "summary": f"[LLM processing failed: {str(e)}]",
            "citations": [],
            "why_these": "System fallback: LLM did not return valid output."
        }
