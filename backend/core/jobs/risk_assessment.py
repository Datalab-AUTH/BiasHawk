"""
NIST AI RMF risk assessment handler.

Assembles everything the earlier jobs produced for this instance, runs the
pipeline over it, and stores the report. The old service received all of this
as a RabbitMQ payload the API had to gather and serialise first; here it reads
the models directly.
"""

import logging

from core.jobs._dataset import load_dataset
from core.models import InstanceDataDrift
from core.risk import knowledge_base, pipeline

log = logging.getLogger("core.jobs.risk_assessment")


def _quality_metrics_for_pipeline(instance):
    """
    Reshape quality metrics into the layout the analyser expects.

    The old data-quality service emitted one flat mapping of feature name to
    metrics with a "Dataset Level" pseudo-feature holding the totals. Phase 2
    stores those totals separately under "dataset", which is cleaner but not
    what DocumentAnalyzerAgent reads, so rebuild the old shape here rather than
    editing the ported analyser.
    """
    metrics = instance.quality_metrics or {}
    features = metrics.get("features") or {}
    dataset = metrics.get("dataset") or {}

    flat = dict(features)
    flat["Dataset Level"] = {
        "Total Rows": dataset.get("total_rows", 0),
        "Duplicate Row Count": dataset.get("duplicate_rows", 0),
        "Total Columns": dataset.get("total_columns", 0),
    }
    return flat


def _drift_for_pipeline(instance):
    """Most recent drift record where this instance is the comparison side."""
    record = (
        InstanceDataDrift.objects.filter(comparison_instance=instance)
        .order_by("-created_at")
        .first()
    )
    if record is None:
        return None, None
    return (record.data_drift_metrics or None), (record.bias_drift_events or None)


def run(job):
    instance = job.instance
    if instance is None:
        raise ValueError("risk_assessment requires an instance.")

    # Static public corpus, embedded once. Idempotent after the first run.
    knowledge_base.ingest()

    drift_metrics, bias_drift_events = _drift_for_pipeline(instance)

    input_data = {
        "ai_system_documentation": instance.usecase.metadata or None,
        "data_compliance_form": instance.metadata or None,
        "data_profile_metrics": None,
        "data_quality_metrics": _quality_metrics_for_pipeline(instance),
        "bias_assessment_results": instance.analysis_results or None,
        "drift_metrics": drift_metrics,
        "bias_drift_events": bias_drift_events,
    }

    present = [key for key, value in input_data.items() if value]
    log.info("Risk assessment for instance %s with: %s", instance.id, ", ".join(present))
    if not (input_data["data_quality_metrics"] or input_data["bias_assessment_results"]):
        raise ValueError(
            "Nothing to assess. Run data_quality and bias_assessment on this instance first."
        )

    state = pipeline.run(input_data)

    report = (state.get("final_report") or {}).get("full_report_markdown", "")
    if not report:
        raise RuntimeError("The risk pipeline produced no report.")

    actions = state.get("prioritized_actions") or []
    actions = [a.model_dump() if hasattr(a, "model_dump") else a for a in actions]

    summary = state.get("risk_summary") or {}
    critical = summary.get("critical_count", 0)
    high = summary.get("high_count", 0)
    medium = summary.get("medium_count", 0)
    low = summary.get("low_count", 0)

    if critical:
        level, score = "CRITICAL", 90 + min(critical * 2, 10)
        justification = f"System has {critical} critical risk(s) requiring immediate attention"
    elif high:
        level, score = "HIGH", 70 + min(high * 5, 20)
        justification = f"System has {high} high-priority risk(s) requiring prompt action"
    elif medium:
        level, score = "MEDIUM", 40 + min(medium * 5, 30)
        justification = f"System has {medium} medium-level risk(s) requiring monitoring"
    else:
        level, score = "LOW", 10 + min(low * 5, 30)
        justification = f"System has {low} low-level risk(s) with an acceptable risk profile"

    structured = {
        "overall_risk_level": {
            "level": level,
            "score": score,
            "justification": justification,
        },
        "critical_findings": [
            f"{a.get('risk_category', 'Unknown')}: {a.get('risk_description', 'No description')}"
            for a in actions[:5]
            if isinstance(a, dict)
        ],
        "prioritized_actions": actions,
        "governance_analysis": state.get("governance_analysis", {}),
        "quality_analysis": state.get("quality_analysis", {}),
        "bias_analysis": state.get("bias_analysis", {}),
        "drift_analysis": state.get("drift_analysis", {}),
        "nist_mapping": state.get("nist_mapping", {}),
    }

    instance.nist_risk_report = report
    instance.nist_risk_report_data = structured
    instance.save(update_fields=["nist_risk_report", "nist_risk_report_data", "updated_at"])

    return {
        "risk_level": level,
        "risk_score": score,
        "prioritized_actions": len(actions),
        "report_chars": len(report),
        "inputs": present,
    }
