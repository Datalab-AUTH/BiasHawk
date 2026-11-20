"""
Sensitive feature detection handler.

Scores every column against the knowledge base and the model, and stores the
sensitive ones on the instance for the bias assessment to use.
"""

import logging

from core.analysis import sensitive
from core.jobs._dataset import load_dataset

log = logging.getLogger("core.jobs.sensitive_features")


def run(job):
    instance = job.instance
    if instance is None:
        raise ValueError("sensitive_features requires an instance.")

    df, dataset = load_dataset(instance)

    # csv_features holds the descriptions a user typed against each column;
    # fall back to the header when nothing has been filled in.
    descriptions = dict(dataset.csv_features or {})
    for column in df.columns:
        descriptions.setdefault(str(column), "")

    log.info("Assessing %d features on instance %s", len(descriptions), instance.id)
    findings = sensitive.analyse_features(descriptions)

    instance.dataset_sensitive_features = {
        finding["feature_name"]: {
            "score": finding["overall_assessment_score"],
            "by_keyword": finding["is_sensitive_by_keyword"],
            "by_llm": finding["is_sensitive_by_llm"],
            "categories": [
                detail["category_name"] for detail in finding["identified_categories_details"]
            ],
            "summary": finding["llm_assessment_summary"],
            "details": finding["identified_categories_details"],
        }
        for finding in findings
    }
    instance.save(update_fields=["dataset_sensitive_features", "updated_at"])

    return {
        "features_assessed": len(descriptions),
        "sensitive_found": len(findings),
        "top": [f["feature_name"] for f in findings[:5]],
    }
