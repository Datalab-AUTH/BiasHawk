"""
Bias and fairness assessment handler.

Needs a target label, a favourable outcome and the sensitive features. These
come from the job payload; the sensitive features fall back to whatever the
sensitive_features job already stored on the instance.
"""

import logging

from core.analysis.bias import perform_bias_assessment
from core.jobs._dataset import load_dataset

log = logging.getLogger("core.jobs.bias_assessment")


def _resolve_sensitive_features(job, instance, df):
    """Payload wins; otherwise use what sensitive_features detected."""
    requested = job.payload.get("sensitive_features")
    if requested:
        features = [str(f) for f in requested]
    else:
        features = list((instance.dataset_sensitive_features or {}).keys())

    if not features:
        raise ValueError(
            "No sensitive features available. Run the sensitive_features job first, "
            "or pass sensitive_features in the job payload."
        )

    missing = [f for f in features if f not in df.columns]
    if missing:
        raise ValueError(f"Sensitive features not present in the dataset: {', '.join(missing)}")
    return features


def run(job):
    instance = job.instance
    if instance is None:
        raise ValueError("bias_assessment requires an instance.")

    df, _ = load_dataset(instance)

    label = job.payload.get("label")
    favorable_outcome = job.payload.get("favorable_outcome")
    if not label:
        raise ValueError("bias_assessment requires 'label' in the job payload.")
    if label not in df.columns:
        raise ValueError(f"Label column {label!r} is not in the dataset.")
    if favorable_outcome is None:
        raise ValueError("bias_assessment requires 'favorable_outcome' in the job payload.")

    features = _resolve_sensitive_features(job, instance, df)
    log.info(
        "Assessing bias on instance %s: label=%r favourable=%r features=%s",
        instance.id, label, favorable_outcome, features,
    )

    outcome = perform_bias_assessment(
        df,
        sensitive_features=features,
        favorable_outcome=favorable_outcome,
        label=label,
    )
    if not outcome.get("success"):
        raise RuntimeError(outcome.get("error") or "Bias assessment failed.")

    instance.analysis_results = outcome["analysis_results"]
    instance.metrics_report = outcome["metrics_report"]
    instance.warnings_report = outcome["warnings_report"]
    instance.save(
        update_fields=["analysis_results", "metrics_report", "warnings_report", "updated_at"]
    )

    summary = {
        "label": label,
        "favorable_outcome": favorable_outcome,
        "sensitive_features": features,
        "warnings": len(outcome.get("warnings") or []),
        "analyses": sorted(outcome["analysis_results"].keys()),
    }

    # The metrics and warnings reports are the raw material for the executive
    # report, and they have just changed. Write it straight away rather than
    # leaving a stale one on the instance until somebody presses a button.
    if job.payload.get("chain_report", True):
        from core.jobs import enqueue

        follow_up, created = enqueue("bias_report", user=job.user, instance=instance)
        summary["report_job"] = str(follow_up.id)
        summary["report_queued"] = created

    # The risk assessment reads these results; they have just changed, so it is
    # requeued rather than left showing the risk profile of older numbers.
    if job.payload.get("chain_risk", True):
        from core.jobs import enqueue

        risk_job, risk_created = enqueue("risk_assessment", user=job.user, instance=instance)
        summary["risk_job"] = str(risk_job.id)
        summary["risk_queued"] = risk_created

    return summary
