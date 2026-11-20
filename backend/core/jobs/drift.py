"""
Drift handler: data drift and bias drift between two instances of a use case,
plus the unified report over both.

The job's `instance` is the comparison (later) instance; the baseline is named
in the payload as `initial_instance`.
"""

import json
import logging

from core import llm
from core.analysis.bias_drift import perform_bias_drift_analysis
from core.analysis.data_drift import perform_drift_analysis
from core.jobs._dataset import load_dataset
from core.models import Instance, InstanceDataDrift

log = logging.getLogger("core.jobs.drift")

SYSTEM_PROMPT = (
    "You are a senior ML monitoring analyst specialising in AI risk, data drift and "
    "algorithmic fairness. You are given reports on both data drift (changes in "
    "feature distributions) and bias drift (changes in fairness and performance "
    "disparity metrics). Synthesise them into a single cohesive professional "
    "Markdown report explaining the situation, the combined risks, and actionable "
    "recommendations for business and technical stakeholders. Focus on the interplay "
    "between the two kinds of drift. Do not include any author signature, footer or date."
)

USER_PROMPT = """\
Analyse the following data drift and bias drift reports and produce one unified
Markdown report.

--- BEGIN DATA DRIFT SECTION ---

### DATA DRIFT METRICS (JSON) ###
{data_metrics}

### DATA DRIFT SUMMARY ###
{data_summary}

### DATA DRIFT WARNINGS ###
{data_warnings}

--- END DATA DRIFT SECTION ---

--- BEGIN BIAS DRIFT SECTION ---

### BIAS DRIFT RESULTS (JSON) ###
{bias_events}

### BIAS DRIFT SUMMARY (MARKDOWN) ###
{bias_summary}

--- END BIAS DRIFT SECTION ---

Structure the report as follows:

1. **Executive Summary** , overall model health across both kinds of drift, an
   overall risk level (Low, Moderate, High), and the key areas of concern.

2. **Detailed Drift Analysis**
   - *Data Drift Findings*: which features drifted and how severely.
   - *Bias & Fairness Drift Findings*: which fairness metrics worsened, naming
     Statistical Parity, Disparate Impact or F1-score disparity specifically.

3. **Impact Assessment** , business and technical impact, and above all the
   interplay between the two: does a drifted feature correlate with a worsening
   fairness metric? Identify the subgroups needing immediate attention.

4. **Recommended Actions** , prioritised: Immediate (high priority), Next Steps
   (medium priority), and Monitoring Adjustments.

5. **Conclusion** , the model's current state and why the actions matter.
"""


def _resolve_baseline(job, instance):
    baseline_id = job.payload.get("initial_instance")
    if not baseline_id:
        raise ValueError("drift requires 'initial_instance' in the job payload.")

    # Scoped to the same use case, which also scopes it to the same owner.
    baseline = Instance.objects.filter(
        usecase=instance.usecase, pk=baseline_id
    ).first()
    if baseline is None:
        raise ValueError(
            f"Baseline instance {baseline_id} is not part of use case {instance.usecase_id}."
        )
    if baseline.pk == instance.pk:
        raise ValueError("The baseline and comparison instances must be different.")
    return baseline


def run(job):
    instance = job.instance
    if instance is None:
        raise ValueError("drift requires an instance.")

    baseline = _resolve_baseline(job, instance)
    baseline_df, _ = load_dataset(baseline)
    comparison_df, _ = load_dataset(instance)

    log.info("Drift: baseline %s vs comparison %s", baseline.id, instance.id)

    data_drift = perform_drift_analysis(baseline_df, comparison_df)
    if not data_drift.get("success"):
        raise RuntimeError(data_drift.get("error") or "Data drift analysis failed.")

    # Bias drift needs both instances to have been assessed already. It is
    # optional: a pair with no bias assessment still gets the data drift half.
    bias_drift = {}
    if baseline.analysis_results and instance.analysis_results:
        bias_drift = perform_bias_drift_analysis(
            baseline.analysis_results, instance.analysis_results
        ) or {}
    else:
        log.info(
            "Skipping bias drift: %s has no bias assessment.",
            "baseline" if not baseline.analysis_results else "comparison instance",
        )

    bias_events = bias_drift.get("drift_events", []) or []
    bias_summary = bias_drift.get("markdown_report", "") or "No bias drift analysis was run."

    report = llm.chat(
        SYSTEM_PROMPT,
        USER_PROMPT.format(
            data_metrics=json.dumps(data_drift.get("metrics", {}), default=str)[:12000],
            data_summary=data_drift.get("summary", ""),
            data_warnings=json.dumps(data_drift.get("warnings", []), default=str)[:8000],
            bias_events=json.dumps(bias_events, default=str)[:8000],
            bias_summary=bias_summary,
        ),
    )

    record, _ = InstanceDataDrift.objects.update_or_create(
        initial_instance=baseline,
        comparison_instance=instance,
        defaults={
            "drift_detected": bool(data_drift.get("drift_detected")),
            "data_drift_summary": data_drift.get("markdown_summary", ""),
            "data_drift_warnings": json.dumps(data_drift.get("warnings", []), default=str),
            "data_drift_metrics": json.loads(
                json.dumps(data_drift.get("metrics", {}), default=str)
            ),
            "bias_drift_detected": bool(bias_events),
            "bias_drift_events": json.loads(json.dumps(bias_events, default=str)),
            "bias_drift_summary": bias_summary,
            "final_drift_report": report,
        },
    )

    return {
        "drift_record": str(record.id),
        "baseline": str(baseline.id),
        "data_drift_detected": record.drift_detected,
        "data_drift_warnings": data_drift.get("total_warnings", 0),
        "bias_drift_events": len(bias_events),
        "report_chars": len(report),
    }
