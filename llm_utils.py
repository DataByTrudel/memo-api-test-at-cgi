# llm_utils.py
import openai
import os

openai.api_type = "azure"
openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
openai.api_key = os.getenv("AZURE_OPENAI_KEY")
openai.api_version = "2023-07-01-preview"  # or newer if you’ve enabled it

def prepare_llm_input(question: str, ask_response: dict) -> dict:
    documents = []
    for result in ask_response.get("results", []):
        documents.append({
            "filename": result.get("metadata_storage_path", "unknown").split("/")[-1],
            "page": 1,
            "content": result.get("content_preview", "")
        })

    return {
        "question": question,
        "documents": documents
    }


    return {
        "question": question,
        "documents": documents,
        "instructions": {
            "honor_supersession": True,
            "output_format": "acheron_json"
        }
    }

def load_prompt_template(corpus: str) -> str:
    prompt_lookup = {
        "memos": "prompt_memo.txt",
        "statutes": "prompt_ch32.txt"
    }

    prompt_file = prompt_lookup.get(corpus, "prompt_acheron.txt")
    print(f"📄 Using prompt: {prompt_file} for corpus: '{corpus}'")

    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read()

import json
import re

def extract_clean_json(response_text: str) -> dict:
    """
    Extracts and parses JSON from LLM output, stripping markdown formatting if present.
    """
    # Remove ```json ... ``` or ``` blocks
    cleaned = re.sub(r"```(json)?", "", response_text).strip()

    # Try to parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {str(e)}\nRaw content: {cleaned}")


from openai import AzureOpenAI
import os

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version="2023-07-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def call_gpt(llm_input: dict) -> dict:
    prompt_template = load_prompt_template()

    doc_block = "\n\n".join(
        f"{doc['filename']} (p. {doc['page']}):\n{doc['content']}"
        for doc in llm_input["documents"]
    )

    full_prompt = f"{prompt_template}\n\nUser question: {llm_input['question']}\n\nRetrieved memo pages:\n{doc_block}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Use your Azure deployment name
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
