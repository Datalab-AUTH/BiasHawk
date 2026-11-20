"""
Data quality handler.

The old pipeline for this was: Django publishes to RabbitMQ, the data-quality
container consumes it, downloads the CSV over HTTP from BACKEND_MEDIA_URL,
computes, publishes a response, and backend-rmq-receiver consumes that and
writes to the Instance. Five hops and two containers.

Here: read the file off disk, compute, save.
"""

import logging

import pandas as pd

from core import llm
from core.analysis import quality
from core.models import InstanceDatasetFile

log = logging.getLogger("core.jobs.data_quality")

SYSTEM_PROMPT = "You are a data analyst generating a data quality report."

REPORT_PROMPT = """\
You are a helpful data analyst assistant. Your task is to generate a
comprehensive data quality report in Markdown format based on the provided
metrics summary and warnings list.

**Input Data:**

**1. Data Quality Metrics Summary:**
{metrics}

**2. Data Quality Warnings:**
{warnings}

**Instructions:**
Please structure the report with the following sections:

## 1. Executive Summary
Briefly summarize the overall data quality status, highlighting the most
critical findings or areas of concern.

## 2. Detailed Findings (Based on Metrics)
Discuss the key observations from the metrics summary table. Comment on missing
data, variability (unique values), data types, duplicates, and basic
statistics. Mention specific features if they stand out, e.g. high missingness
or low variability.

## 3. Warnings Analysis
List and explain the generated warnings. Describe the potential impact of each
type of warning found, e.g. the impact of outliers, duplicate rows, mixed
types. Refer to specific features mentioned in the warnings. If no warnings
were generated, state that clearly.

## 4. Recommendations
Based on the findings and warnings, provide actionable recommendations for data
cleaning, preprocessing, or further investigation. Prioritize them by severity
or potential impact. If the data quality is generally good, say so and suggest
minor checks.

Format: use Markdown for clear structure (headings, lists, bold text). Be
concise yet informative. Focus on explaining the implications of the metrics
and warnings.
"""

# Beyond these the prompt costs more than it informs; send head and tail
# instead. The old service used the same two limits.
MAX_METRICS_CHARS = 10000
MAX_WARNINGS_CHARS = 8000


def _as_markdown(frame, empty_message, limit, index):
    if frame is None or frame.empty:
        return empty_message
    table = frame.to_markdown(index=index, numalign="left", stralign="left")
    if len(table) <= limit:
        return table
    log.info("Table of %d chars truncated for the prompt.", len(table))
    return (
        frame.head().to_markdown(index=index)
        + "\n...\n"
        + frame.tail().to_markdown(index=index)
    )


def run(job):
    instance = job.instance
    if instance is None:
        raise ValueError("data_quality requires an instance.")

    dataset = (
        InstanceDatasetFile.objects.filter(
            instance=instance, kind=InstanceDatasetFile.SOURCE
        )
        .order_by("-created_at")
        .first()
    )
    if dataset is None:
        raise ValueError(f"Instance {instance.id} has no source dataset to analyse.")

    log.info("Reading %s for instance %s", dataset.file.name, instance.id)
    with dataset.file.open("rb") as handle:
        df = pd.read_csv(handle)

    metrics, warnings, metrics_frame, warnings_frame = quality.analyse(df)
    log.info(
        "Instance %s: %d rows, %d columns, %d warnings",
        instance.id, metrics["dataset"]["total_rows"],
        metrics["dataset"]["total_columns"], len(warnings),
    )

    warnings_display = warnings_frame
    if not warnings_frame.empty and "data" in warnings_frame.columns:
        warnings_display = warnings_frame.copy()
        warnings_display["data"] = warnings_display["data"].astype(str)

    report = llm.chat(
        SYSTEM_PROMPT,
        REPORT_PROMPT.format(
            metrics=_as_markdown(
                metrics_frame,
                "No metrics summary available.",
                MAX_METRICS_CHARS,
                index=True,
            ),
            # Warnings carry no meaningful index, so the old report left the
            # row numbers off this table.
            warnings=_as_markdown(
                warnings_display,
                "No warnings generated.",
                MAX_WARNINGS_CHARS,
                index=False,
            ),
        ),
    )

    instance.quality_metrics = metrics
    instance.quality_warnings = warnings
    instance.data_quality_report = report
    instance.save(
        update_fields=[
            "quality_metrics",
            "quality_warnings",
            "data_quality_report",
            "updated_at",
        ]
    )

    summary = {
        "rows": metrics["dataset"]["total_rows"],
        "columns": metrics["dataset"]["total_columns"],
        "warnings": len(warnings),
        "report_chars": len(report),
    }

    # The risk assessment reads these results; they have just changed, so it is
    # requeued rather than left showing the risk profile of older numbers.
    if job.payload.get("chain_risk", True):
        from core.jobs import enqueue

        risk_job, risk_created = enqueue("risk_assessment", user=job.user, instance=instance)
        summary["risk_job"] = str(risk_job.id)
        summary["risk_queued"] = risk_created

    return summary
