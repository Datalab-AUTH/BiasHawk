"""
Retrieval and answering.

The chain is the same one the old RAG service ran: optional HyDE, vector search
by L2 distance, cross-encoder rerank, then an answer grounded only in the
retrieved passages. What changed is that it is a function call rather than a
RabbitMQ request/response , the agents used to publish a message and block on
`wait_for_response(timeout=60)` for exactly this.
"""

import logging

from django.conf import settings
from pgvector.django import L2Distance

from core import llm
from core.models import DocumentChunk
from core.rag import embeddings

log = logging.getLogger("core.rag")

HYDE_SYSTEM = "You write short factual passages."

HYDE_PROMPT = """\
Write a short, concise passage that directly answers the question below. Write
it as an ideal answer even if you have to invent specifics , it is used only to
find similar real documents, never shown to anyone. Do not preface it with
"Here is a passage" or similar; give only the passage.

Question: {query}

Passage:"""

ANSWER_SYSTEM = (
    "You are a helpful AI assistant. Answer based only on the provided context. "
    "If the context does not contain the answer, say so. Do not make up "
    "information. Be concise. Cite the source where you can, like "
    "(Source File: <filename>, Chunk: <number>)."
)

ANSWER_PROMPT = """\
Context:
{context}

Question: {query}

Answer:"""


def _hypothetical_document(query):
    """HyDE: a hypothetical answer embeds closer to real answers than a question does."""
    try:
        return llm.chat(HYDE_SYSTEM, HYDE_PROMPT.format(query=query), max_retries=1)
    except Exception as exc:
        log.warning("HyDE generation failed (%s); embedding the query itself.", exc)
        return query


def retrieve(*, usecase, instance=None, query, top_k=None, use_hyde=None):
    """Nearest chunks within one scope, reranked."""
    top_k = top_k or settings.RAG_TOP_K
    use_hyde = settings.RAG_USE_HYDE if use_hyde is None else use_hyde

    text_to_embed = _hypothetical_document(query) if use_hyde else query
    vector = embeddings.embed_query(text_to_embed)

    rows = (
        DocumentChunk.objects.for_scope(usecase=usecase, instance=instance)
        .annotate(distance=L2Distance("embedding", vector))
        .order_by("distance")[:top_k]
    )

    chunks = [
        {
            "id": str(row.id),
            "text": row.chunk_text,
            "source": row.document_name,
            "chunk_number": row.chunk_number,
            "metadata": row.metadata,
            "distance": float(row.distance),
        }
        for row in rows
    ]
    log.info("Retrieved %d chunk(s) for %r (hyde=%s)", len(chunks), query[:60], use_hyde)
    return embeddings.rerank(query, chunks, settings.RAG_TOP_N_RERANK)


def answer(*, usecase, instance=None, query, top_k=None, use_hyde=None):
    """Retrieve, then answer strictly from what was retrieved."""
    chunks = retrieve(
        usecase=usecase, instance=instance, query=query, top_k=top_k, use_hyde=use_hyde
    )

    if chunks:
        context = "\n\n".join(
            f"Source File: {c['source']} (Chunk {c['chunk_number']})\nContent: {c['text']}"
            for c in chunks
        )
    else:
        context = "No relevant information was found in the provided documents."

    text = llm.chat(ANSWER_SYSTEM, ANSWER_PROMPT.format(context=context, query=query))
    return {
        "answer": text,
        "chunks": chunks,
        "sources": sorted({c["source"] for c in chunks}),
    }
