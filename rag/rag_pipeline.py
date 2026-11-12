"""Retrieval-augmented generation over the disaster records.

Retrieves the most relevant records from ChromaDB and asks a language model
to answer from them. Generation backends, in order of preference:
    1. A local Ollama server (config.OLLAMA_MODEL)
    2. google/flan-t5-small through Hugging Face transformers
    3. An extractive answer that just lists the retrieved records

Run directly with:  python -m rag.rag_pipeline "major flood disaster"
"""

import sys

import requests

import config
from utils.helpers import get_logger, now_iso, save_json
from vectordb.search import search


log = get_logger("rag")


PROMPT_TEMPLATE = """You are a disaster monitoring assistant. Answer the question using only the reports below. Mention locations and severity where the reports give them, and say so if the reports do not contain the answer. Be concise.

Reports:
{context}

Question: {question}

Answer:"""

_fallback_model = None


def format_context(hits):

    lines = []

    for index, hit in enumerate(hits, start=1):
        details = ", ".join(
            str(hit[field])
            for field in ("disaster_type", "severity", "source", "published_at")
            if hit.get(field)
        )
        lines.append(f"{index}. {hit['text']} ({details})")

    return "\n".join(lines)


def generate_with_ollama(prompt):

    response = requests.post(
        f"{config.OLLAMA_URL}/api/generate",
        json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=config.OLLAMA_TIMEOUT,
    )
    response.raise_for_status()

    return response.json()["response"].strip()


def generate_with_transformers(prompt):

    global _fallback_model

    if _fallback_model is None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        _fallback_model = (
            AutoTokenizer.from_pretrained(config.FALLBACK_LLM),
            AutoModelForSeq2SeqLM.from_pretrained(config.FALLBACK_LLM),
        )

    tokenizer, model = _fallback_model

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    output = model.generate(**inputs, max_new_tokens=150)

    return tokenizer.decode(output[0], skip_special_tokens=True).strip()


def generate_extractive(hits):

    lines = ["Most relevant reports:"]

    for hit in hits:
        lines.append(f"- [{hit.get('severity', 'unknown')}] {hit.get('headline', hit['text'])} ({hit.get('source', '')})")

    return "\n".join(lines)


def generate(prompt, hits):
    """Return (answer, backend name), falling through the backends on failure."""

    backends = (
        (f"ollama:{config.OLLAMA_MODEL}", lambda: generate_with_ollama(prompt)),
        (config.FALLBACK_LLM, lambda: generate_with_transformers(prompt)),
    )

    for name, backend in backends:

        try:
            answer = backend()
            if answer:
                return answer, name
        except Exception as error:
            log.warning("%s unavailable: %s", name, error)

    return generate_extractive(hits), "extractive"


def answer_question(question, n_results=5, **filters):

    hits = search(question, n_results=n_results, **filters)

    if not hits:
        return {
            "question": question,
            "answer": "No disaster reports are stored yet. Run the pipeline first.",
            "backend": None,
            "sources": [],
        }

    prompt = PROMPT_TEMPLATE.format(context=format_context(hits), question=question)

    answer, backend = generate(prompt, hits)

    return {"question": question, "answer": answer, "backend": backend, "sources": hits}


def situation_report():
    """Generate the standing situation report and save it for the dashboard."""

    report = answer_question(config.SITUATION_REPORT_QUERY, n_results=8, severity="high")

    if not report["sources"]:
        report = answer_question(config.SITUATION_REPORT_QUERY, n_results=8)

    report["generated_at"] = now_iso()

    save_json(config.REPORT_FILE, report)

    return report


if __name__ == "__main__":

    result = answer_question(" ".join(sys.argv[1:]) or "major flood disaster")

    print("\nGenerated Response:\n")
    print(result["answer"])

    print("\nSources:")
    for source in result["sources"]:
        print(f"- {source.get('headline', source['text'])} ({source.get('source', '')})")
