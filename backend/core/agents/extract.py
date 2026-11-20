"""
Metadata extraction from uploaded documents.

The old agents were Google ADK `SequentialAgent`s over `LiteLlm("openai/...")`:
a query agent that called a RAG tool once per question and wrote prose answers
into session state, then a formatter agent that read that prose back and emitted
JSON. Two LLM passes, the second one parsing the first one's summaries.

This does it in one. Each question is used for *retrieval only* , embed, vector
search, rerank, no completion , and the deduplicated passages are then handed to
a single call that fills the schema directly from the source text. That is
roughly 25 completions fewer per extraction, and it removes an intermediate
summarisation step where facts were being lost before the formatter ever saw
them.
"""

import json
import logging
import re

from pydantic import ValidationError

from core import llm
from core.rag import query as rag_query

log = logging.getLogger("core.agents")

# Enough context to answer from, without sending the whole corpus every time.
MAX_CONTEXT_CHARS = 40000

SYSTEM_PROMPT = (
    "You extract structured compliance metadata from technical documentation. "
    "You output a single valid JSON object and nothing else , no explanation, no "
    "preamble, no code fence. Every value must come from the provided context. "
    "Never invent a name, date, organisation or figure that is not present."
)

USER_PROMPT = """\
Below are excerpts from documentation for an AI system, retrieved to answer a
fixed set of compliance questions.

--- BEGIN CONTEXT ---
{context}
--- END CONTEXT ---

The questions this record must answer:
{questions}

Produce a single JSON object matching exactly this structure:

{schema}

Rules:
- Use only what the context supports.
- Where the context does not answer a field, use "unknown" for strings, false
  for booleans, and ["unknown"] for arrays. Never guess.
- Arrays must always be arrays, even when unknown.
- Output only the JSON object, starting with {{ and ending with }}.
"""

RETRY_PROMPT = """\
That reply did not match the required structure:

{errors}

Return the corrected JSON object only.
"""


def _extract_json(text):
    """Models add code fences despite instructions; tolerate that."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in the model's reply.")
    return json.loads(text[start : end + 1])


def gather_evidence(*, usecase, instance, questions):
    """
    Retrieve once per question and deduplicate.

    Retrieval only , no completion per question. Different questions surface
    overlapping passages, so the union is far smaller than questions x top_n.
    """
    found = {}
    for question in questions:
        for chunk in rag_query.retrieve(
            usecase=usecase, instance=instance, query=question, use_hyde=False
        ):
            found.setdefault(chunk["id"], chunk)

    ordered = sorted(found.values(), key=lambda c: c["distance"])
    log.info("Gathered %d unique passage(s) from %d question(s)", len(ordered), len(questions))
    return ordered


def build_context(chunks):
    parts, total = [], 0
    for chunk in chunks:
        block = (
            f"Source File: {chunk['source']} (Chunk {chunk['chunk_number']})\n"
            f"{chunk['text']}"
        )
        if total + len(block) > MAX_CONTEXT_CHARS:
            log.info("Context capped at %d chars", total)
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


def extract(*, usecase, instance, questions, schema):
    """
    Fill `schema` from the documents ingested for this scope.

    Returns (model instance, stats). Raises if nothing has been ingested.
    """
    chunks = gather_evidence(usecase=usecase, instance=instance, questions=questions)
    if not chunks:
        raise ValueError(
            "No document passages found. Run the rag_ingest job before extracting metadata."
        )

    context = build_context(chunks)
    skeleton = json.dumps(schema().model_dump(), indent=2)
    prompt = USER_PROMPT.format(
        context=context,
        questions="\n".join(f"- {q}" for q in questions),
        schema=skeleton,
    )

    errors = None
    for attempt in (1, 2):
        message = prompt if errors is None else prompt + RETRY_PROMPT.format(errors=errors)
        reply = llm.chat(SYSTEM_PROMPT, message)
        try:
            parsed = schema.model_validate(_extract_json(reply))
            log.info("Extraction validated on attempt %d", attempt)
            return parsed, {
                "passages_used": len(context.split("Source File:")) - 1,
                "passages_found": len(chunks),
                "context_chars": len(context),
                "attempts": attempt,
            }
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            errors = str(exc)[:2000]
            log.warning("Extraction attempt %d did not validate: %s", attempt, errors[:200])

    raise RuntimeError(f"The model did not return a valid record after 2 attempts: {errors}")
