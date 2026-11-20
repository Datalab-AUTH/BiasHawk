"""Job enqueueing and dispatch."""

import logging

from core.models import Job

log = logging.getLogger("core.jobs")

# Kinds where a second concurrent run would just fight the first for the same
# rows on the Instance. Re-requesting one returns the job already in flight.
_SINGLETON_KINDS = {
    # Ingestion re-reads every document in the scope, so uploading three files
    # in a row needs one run, not three.
    "rag_ingest",
    "data_governance",
    "data_quality",
    "sensitive_features",
    "bias_assessment",
    "bias_report",
    "risk_assessment",
    "usecase_extract",
    "instance_extract",
}


def enqueue(kind, *, user, instance=None, usecase=None, payload=None):
    """
    Queue a job and return (job, created).

    `created` is False when an equivalent job was already queued or running ,
    the caller gets that one back rather than a duplicate. The old backend
    used update_or_create on the task-state row for this; making it explicit
    keeps the history of previous runs instead of overwriting it.
    """
    if usecase is None and instance is not None:
        usecase = instance.usecase

    if kind in _SINGLETON_KINDS:
        # Only a job that has not started yet can absorb new work: a queued
        # ingest will read whatever files exist when it runs, but one already
        # running has read them, so a file uploaded since needs its own run.
        existing = (
            Job.objects.filter(
                kind=kind, instance=instance, usecase=usecase, status=Job.QUEUED
            )
            .order_by("-created_at")
            .first()
        )
        if existing is not None:
            log.info("Job %s (%s) already queued; not adding a duplicate.", existing.id, kind)
            return existing, False

        if Job.objects.filter(
            kind=kind, instance=instance, usecase=usecase, status=Job.RUNNING
        ).exists():
            log.info("A %s job is running; queueing a follow-up for the newer input.", kind)

    job = Job.objects.create(
        kind=kind,
        user=user,
        usecase=usecase,
        instance=instance,
        payload=payload or {},
    )
    log.info("Queued job %s (%s) for instance %s", job.id, kind, instance.id if instance else None)
    return job, True
