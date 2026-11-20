"""
RAG ingestion handler.

Scope follows the job: a job with an instance ingests that instance's documents,
one with only a use case ingests the use case's. Files are read from MEDIA_ROOT
directly , the old RAG service was handed a list of URLs and downloaded each one
back out of the API it was already colocated with.
"""

import logging

from core.models import InstanceDataFile, UsecaseDataFile
from core.rag.ingest import ingest_documents

log = logging.getLogger("core.jobs.rag_ingest")


def run(job):
    instance = job.instance
    usecase = job.usecase or (instance.usecase if instance else None)
    if usecase is None:
        raise ValueError("rag_ingest requires a use case or an instance.")

    if instance is not None:
        files = InstanceDataFile.objects.filter(instance=instance)
        scope = f"instance {instance.id}"
    else:
        files = UsecaseDataFile.objects.filter(usecase=usecase)
        scope = f"usecase {usecase.id}"

    documents = []
    for data_file in files:
        if not data_file.file:
            continue
        name = data_file.file.name.rsplit("/", 1)[-1]
        documents.append((name, data_file.file.path))

    if not documents:
        raise ValueError(f"No documents uploaded for {scope}.")

    log.info("Ingesting %d document(s) for %s", len(documents), scope)
    summary = ingest_documents(usecase=usecase, instance=instance, documents=documents)
    summary["scope"] = scope

    # Indexing documents is never the goal in itself , it exists so the metadata
    # can be extracted from them. Chain straight into that rather than making
    # someone come back and press a second button.
    if job.payload.get("chain_extraction", True):
        from core.jobs import enqueue

        kind = "instance_extract" if instance is not None else "usecase_extract"
        follow_up, created = enqueue(
            kind, user=job.user, usecase=usecase, instance=instance
        )
        summary["extraction_job"] = str(follow_up.id)
        summary["extraction_queued"] = created

    return summary
