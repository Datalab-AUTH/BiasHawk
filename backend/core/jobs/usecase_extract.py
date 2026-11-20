"""
Use case metadata extraction.

Reads the documents ingested for a use case and fills the AI system
documentation record the dashboard renders.
"""

import logging

from core.agents.extract import extract
from core.agents.schemas import USECASE_QUESTIONS, AISystemDocumentation

log = logging.getLogger("core.jobs.usecase_extract")


def run(job):
    usecase = job.usecase or (job.instance.usecase if job.instance else None)
    if usecase is None:
        raise ValueError("usecase_extract requires a use case.")

    log.info("Extracting system documentation for usecase %s", usecase.id)
    record, stats = extract(
        usecase=usecase,
        instance=None,
        questions=USECASE_QUESTIONS,
        schema=AISystemDocumentation,
    )

    usecase.metadata = record.model_dump()
    usecase.save(update_fields=["metadata", "updated_at"])

    general = record.general_information
    log.info(
        "Extracted %s (%s) for usecase %s",
        general.ai_system_name, general.provider_organization_name, usecase.id,
    )
    return {
        **stats,
        "ai_system_name": general.ai_system_name,
        "provider": general.provider_organization_name,
    }
