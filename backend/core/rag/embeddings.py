"""
Embeddings and reranking.

Embeddings come from Open WebUI , the same server, base URL and API key that
serve chat. The model runs on the server's GPU, so the API and worker containers
hold no embedding weights and reserve no CPU for them. This replaces an
in-process sentence-transformers `SentenceTransformer` that loaded
nomic-embed-text onto the CPU in every one of the runner's eight threads.

Reranking is still in-process: Open WebUI exposes no reranking endpoint, and the
cross-encoder is a 22M-parameter MiniLM rather than a full embedding model. It
is cached at module level , it takes seconds to read from disk.
"""

import logging
import math
import threading
import time

from django.conf import settings

from core import llm

log = logging.getLogger("core.rag")

_reranker = None
_lock = threading.Lock()


class EmbeddingError(RuntimeError):
    pass


def _unit(vector):
    """
    Scale to unit length.

    Retrieval orders by L2 distance, which only agrees with cosine similarity
    when the vectors are normalised , the guarantee `normalize_embeddings=True`
    used to provide. Open WebUI already returns unit vectors for this model;
    this keeps the invariant true regardless of what serves it.
    """
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise EmbeddingError("Embedding model returned a zero vector.")
    return [value / norm for value in vector]


def embed_documents(texts, *, max_retries=3):
    """
    Embed a batch of texts, in the order given.

    Callers batch before calling this , see EMBED_BATCH in `rag.ingest` and
    `risk.knowledge_base`. Raises EmbeddingError rather than returning partial
    results, so a failing ingest is recorded as failed and retried instead of
    storing chunks that cannot be searched.
    """
    texts = list(texts)
    if not texts:
        return []

    client = llm.get_client()
    model = settings.OPENWEBUI_EMBED_MODEL
    delay = 5
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            started = time.monotonic()
            response = client.embeddings.create(model=model, input=texts)
            # The response is not required to preserve request order; `index` is.
            items = sorted(response.data, key=lambda item: item.index)
            if len(items) != len(texts):
                raise EmbeddingError(
                    f"Asked {model} for {len(texts)} embeddings, got {len(items)}."
                )
            vectors = [_unit(list(item.embedding)) for item in items]
            log.info(
                "embed model=%s attempt=%d elapsed=%.1fs texts=%d",
                model, attempt, time.monotonic() - started, len(texts),
            )
            break
        except Exception as exc:
            last_error = exc
            log.warning("embed attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
    else:
        raise EmbeddingError(
            f"Open WebUI embedding call failed after {max_retries} attempts: {last_error}"
        )

    # A width mismatch is a configuration error, not a transient one, so it is
    # checked after the retry loop rather than inside it.
    actual = len(vectors[0])
    if actual != settings.EMBEDDING_DIM:
        raise EmbeddingError(
            f"{model} produces {actual}-dimensional embeddings but "
            f"DocumentChunk.embedding is VECTOR({settings.EMBEDDING_DIM}). "
            f"Set EMBEDDING_DIM={actual}, migrate, and re-ingest every document , "
            f"chunks embedded with a different model cannot be searched with this one."
        )
    return vectors


def embed_query(text):
    return embed_documents([text])[0]


def get_reranker():
    global _reranker
    if _reranker is None:
        with _lock:
            if _reranker is None:
                from sentence_transformers import CrossEncoder

                log.info("Loading reranker %s (first use)", settings.RERANKER_MODEL)
                _reranker = CrossEncoder(settings.RERANKER_MODEL)
    return _reranker


def rerank(query, chunks, top_n):
    """
    Order chunks by cross-encoder relevance and keep the best `top_n`.

    A reranker failure degrades to the vector order rather than failing the
    query , the retrieved chunks are still relevant, just less well sorted.
    """
    if not chunks:
        return []
    try:
        scores = get_reranker().predict(
            [(query, chunk["text"]) for chunk in chunks], show_progress_bar=False
        )
    except Exception:
        log.exception("Reranking failed; falling back to vector distance order.")
        return chunks[:top_n]

    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = float(score)
    return sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)[:top_n]
