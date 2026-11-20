"""
NIST AI RMF knowledge base, on pgvector.

Replaces the ChromaDB store the old risk-assessment service carried on its own
Docker volume. That store held embeddings of one static 1.1 MB public PDF and was
re-ingested every time the workflow was constructed. Here it is a table in the
application database, embedded once behind an idempotency check, and it drops
chromadb, onnxruntime, kubernetes and the OpenTelemetry stack from the image.
"""

import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pgvector.django import L2Distance

from core.models import NistChunk
from core.rag import embeddings
from core.rag.loaders import load_document

log = logging.getLogger("core.risk")

NIST_PDF = Path(settings.BASE_DIR) / "core" / "data" / "NIST.AI.600-1.pdf"
EMBED_BATCH = 32


def is_ingested():
    return NistChunk.objects.exists()


@transaction.atomic
def ingest(force=False):
    """
    Embed the NIST corpus. Idempotent: a no-op once it is present.

    Returns the number of chunks now stored.
    """
    if is_ingested() and not force:
        count = NistChunk.objects.count()
        log.info("NIST knowledge base already holds %d chunks.", count)
        return count

    if not NIST_PDF.exists():
        raise FileNotFoundError(f"NIST corpus missing at {NIST_PDF}")

    log.info("Ingesting the NIST corpus from %s", NIST_PDF.name)
    NistChunk.objects.all().delete()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, separators=["\n\n", "\n", ". ", " ", ""]
    )

    prepared = []
    for section in load_document(NIST_PDF):
        for piece in splitter.split_text(section["text"]):
            piece = piece.strip()
            if piece:
                prepared.append((section.get("page") or 0, piece))

    rows = []
    for start in range(0, len(prepared), EMBED_BATCH):
        batch = prepared[start : start + EMBED_BATCH]
        vectors = embeddings.embed_documents([text for _, text in batch])
        for (page, text), vector in zip(batch, vectors):
            rows.append(
                NistChunk(
                    document_name=NIST_PDF.name,
                    page=page,
                    chunk_number=len(rows) + 1,
                    chunk_text=text,
                    embedding=vector,
                )
            )
        log.info("Embedded %d/%d NIST chunks", len(rows), len(prepared))

    NistChunk.objects.bulk_create(rows, batch_size=200)
    log.info("NIST knowledge base ready: %d chunks", len(rows))
    return len(rows)


def retrieve(query, n_results=3):
    """Passages of NIST guidance nearest to `query`."""
    if not is_ingested():
        log.warning("NIST knowledge base is empty; returning no guidance.")
        return []

    vector = embeddings.embed_query(query)
    rows = (
        NistChunk.objects.annotate(distance=L2Distance("embedding", vector))
        .order_by("distance")[:n_results]
    )
    return [{"content": row.chunk_text, "metadata": {"page": row.page}} for row in rows]


def guidance_text(query, n_results=3):
    """Retrieved guidance formatted for a prompt, matching the old agent's shape."""
    docs = retrieve(query, n_results)
    return "\n\n".join(
        f"[Source: Page {doc['metadata']['page']}]\n{doc['content']}" for doc in docs
    )
