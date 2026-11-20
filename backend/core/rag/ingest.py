"""
Ingestion: load documents, chunk them, embed, store.

`langchain-text-splitters` is the one LangChain package kept in the project.
RecursiveCharacterTextSplitter has specific separator-hierarchy and overlap
behaviour, and a re-implementation that is nearly right would shift every chunk
boundary and quietly change retrieval quality. It depends only on
langchain-core, which is pure Python.
"""

import logging

from django.conf import settings
from django.db import transaction
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.models import DocumentChunk
from core.rag import embeddings
from core.rag.loaders import load_document

log = logging.getLogger("core.rag")

# Embedding a whole document at once is what exhausts memory on a big upload.
EMBED_BATCH = 32


def _splitter():
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def chunk_document(sections, document_name):
    """Split loaded sections into overlapping passages carrying their origin."""
    splitter = _splitter()
    chunks = []
    for section in sections:
        for piece in splitter.split_text(section["text"]):
            piece = piece.strip()
            if piece:
                chunks.append(
                    {
                        "text": piece,
                        "metadata": {
                            "document_name": document_name,
                            "page": section.get("page"),
                            "chunk_number": len(chunks) + 1,
                        },
                    }
                )
    return chunks


@transaction.atomic
def ingest_documents(*, usecase, instance=None, documents):
    """
    Replace the stored chunks for one scope with freshly embedded ones.

    Args:
        usecase: the Usecase these documents belong to
        instance: an Instance, when ingesting instance-level documents
        documents: [(display name, filesystem path)]

    Returns a summary dict.
    """
    scope = DocumentChunk.objects.filter(usecase=usecase, instance=instance)
    removed = scope.count()
    scope.delete()
    log.info(
        "Ingesting %d document(s) for usecase=%s instance=%s (replacing %d chunks)",
        len(documents), usecase.id, instance.id if instance else None, removed,
    )

    prepared = []
    for name, path in documents:
        sections = load_document(path)
        if not sections:
            log.warning("%s produced no readable text; skipping.", name)
            continue
        prepared.extend((name, chunk) for chunk in chunk_document(sections, name))

    if not prepared:
        raise ValueError("None of the uploaded documents produced readable text.")

    rows = []
    for start in range(0, len(prepared), EMBED_BATCH):
        batch = prepared[start : start + EMBED_BATCH]
        vectors = embeddings.embed_documents([chunk["text"] for _, chunk in batch])
        for (name, chunk), vector in zip(batch, vectors):
            rows.append(
                DocumentChunk(
                    usecase=usecase,
                    instance=instance,
                    document_name=name,
                    chunk_number=chunk["metadata"]["chunk_number"],
                    chunk_text=chunk["text"],
                    embedding=vector,
                    metadata=chunk["metadata"],
                )
            )
        log.info("Embedded %d/%d chunks", min(start + EMBED_BATCH, len(prepared)), len(prepared))

    DocumentChunk.objects.bulk_create(rows, batch_size=200)
    log.info("Stored %d chunks", len(rows))

    return {
        "documents": len({name for name, _ in prepared}),
        "chunks": len(rows),
        "replaced": removed,
    }
