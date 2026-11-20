"""
Instance metadata extraction.

Reads the documents ingested for an instance , its own plus its use case's ,
and fills the data compliance form.
"""

import logging

from core.agents.extract import extract
from core.agents.schemas import INSTANCE_QUESTIONS, AIDataComplianceForm

log = logging.getLogger("core.jobs.instance_extract")


def run(job):
    instance = job.instance
    if instance is None:
        raise ValueError("instance_extract requires an instance.")

    log.info("Extracting the data compliance form for instance %s", instance.id)
    record, stats = extract(
        usecase=instance.usecase,
        instance=instance,
        questions=INSTANCE_QUESTIONS,
        schema=AIDataComplianceForm,
    )

    instance.metadata = record.model_dump()
    instance.save(update_fields=["metadata", "updated_at"])

    overview = record.Data_Overview
    log.info(
        "Extracted data types %s for instance %s", overview.Types_of_Data_Used, instance.id
    )
    return {
        **stats,
        "data_types": overview.Types_of_Data_Used,
        "high_risk": overview.High_Risk_Data_Handling,
    }
