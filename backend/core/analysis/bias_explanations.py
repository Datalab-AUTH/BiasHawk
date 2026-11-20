"""
Plain-language explanations of one bias metric for one feature.

Ported from the old backend's BiasExplanationView. It is rule-based, not an
LLM call: the text is built from the stored results and the thresholds they
were judged against, so it returns at once and always agrees with the
pass/fail verdict the report page shows.
"""

import math

from core.analysis.thresholds import (
    DISPARATE_IMPACT_MAX,
    DISPARATE_IMPACT_MIN,
    STATISTICAL_PARITY_MAX,
    impact_ok,
    parity_ok,
)

BIAS_METRICS = (
    "proxy_identification",
    "sensitive_predictability",
    "performance_discrimination",
    "sensitive_representativity",
    "fairness_metrics",
    "intersectional_performance_discrimination",
    "intersectional_sensitive_representativity",
    "intersectional_fairness_metrics",
)

# How many groups to name before summarising the rest.
MAX_LISTED = 5


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _label(feature):
    """Intersections are stored as "a_&_b"; say "a & b"."""
    return str(feature).replace("_&_", " & ")


def _listed(items):
    shown = ", ".join(items[:MAX_LISTED])
    extra = len(items) - MAX_LISTED
    return f"{shown} and {extra} more" if extra > 0 else shown


def _proxy(feature, results, params):
    threshold = params.get("threshold", 0.7)
    scores = {k: v for k, v in (results or {}).items() if _is_number(v)}
    if not scores:
        return f"No association scores were computed for '{feature}'."

    proxies = sorted(
        ((k, v) for k, v in scores.items() if v > threshold), key=lambda kv: kv[1], reverse=True
    )
    if proxies:
        listed = _listed([f"{k} ({v:.2f})" for k, v in proxies])
        return (
            f"'{feature}' has potential proxy features, with an association above the "
            f"threshold of {threshold}: {listed}. These columns may encode '{feature}' "
            f"indirectly, so a model could discriminate on it even if '{feature}' itself "
            f"is removed from the training data."
        )
    strongest, value = max(scores.items(), key=lambda kv: kv[1])
    return (
        f"No feature is associated with '{feature}' above the threshold of {threshold}; "
        f"the strongest is '{strongest}' at {value:.2f}. Other columns do not strongly "
        f"encode this sensitive attribute, which lowers the risk of proxy discrimination."
    )


def _predictability(feature, value, params):
    threshold = params.get("threshold", 0.5)
    if not _is_number(value):
        return f"Predictability could not be measured for '{feature}': {value}."
    if value > threshold:
        return (
            f"'{feature}' can be predicted from the other features with {value:.0%} accuracy, "
            f"above the threshold of {threshold:.0%}. Information about '{feature}' is spread "
            f"through the rest of the dataset, so a model could learn it indirectly and enable "
            f"proxy discrimination."
        )
    return (
        f"'{feature}' is predicted from the other features with only {value:.0%} accuracy, "
        f"within the threshold of {threshold:.0%}. It cannot easily be inferred from the "
        f"other attributes."
    )


def _performance(feature, results, params, intersectional):
    threshold = params.get("disparity_threshold", 0.2)
    scores = {k: v for k, v in (results or {}).items() if _is_number(v)}
    unscored = len(results or {}) - len(scores)
    subject = (
        f"the combination '{_label(feature)}'" if intersectional else f"'{feature}'"
    )

    if len(scores) < 2:
        return (
            f"There is not enough data to compare model performance across {subject}: "
            f"fewer than two groups had enough rows, with both outcomes present, to score."
        )

    best = max(scores, key=scores.get)
    worst = min(scores, key=scores.get)
    disparity = round(scores[best] - scores[worst], 2)
    note = (
        f" {unscored} group(s) had too little data to score and are not included."
        if unscored
        else ""
    )

    if disparity > threshold:
        return (
            f"Model performance differs across {subject}: the F1-score gap between groups is "
            f"{disparity:.2f}, above the threshold of {threshold}. '{_label(best)}' scores highest "
            f"({scores[best]:.2f}) and '{_label(worst)}' lowest ({scores[worst]:.2f}), so the model "
            f"serves some groups noticeably worse than others.{note}"
        )
    return (
        f"Model performance is consistent across {subject}: the F1-score gap between groups "
        f"is {disparity:.2f}, within the threshold of {threshold}. '{_label(best)}' scores highest "
        f"({scores[best]:.2f}) and '{_label(worst)}' lowest ({scores[worst]:.2f}).{note}"
    )


def _representativity(feature, results, params, intersectional):
    min_pct = params.get("min_pct", 0.01)
    groups = {
        k: v for k, v in (results or {}).items() if isinstance(v, dict) and "percentage" in v
    }
    subject = (
        f"the combination '{_label(feature)}'" if intersectional else f"'{feature}'"
    )
    if not groups:
        return f"No group counts were computed for {subject}."

    under = sorted(
        ((k, v) for k, v in groups.items() if v.get("percentage", 0) < min_pct),
        key=lambda kv: kv[1].get("percentage", 0),
    )
    if under:
        listed = _listed(
            [f"{_label(k)} ({v.get('percentage', 0):.2%}, n={v.get('count', 0)})" for k, v in under]
        )
        return (
            f"Some groups in {subject} are underrepresented, below {min_pct:.0%} of the rows: "
            f"{listed}. With so few examples a model learns little about these groups, which "
            f"tends to mean poorer and less fair predictions for them."
        )
    smallest, info = min(groups.items(), key=lambda kv: kv[1].get("percentage", 0))
    return (
        f"Every group in {subject} makes up at least {min_pct:.0%} of the rows; the smallest "
        f"is '{_label(smallest)}' at {info.get('percentage', 0):.2%} (n={info.get('count', 0)})."
    )


def _fairness(feature, results, params, intersectional):
    if not isinstance(results, dict):
        return f"Fairness metrics are not available for '{_label(feature)}'."
    if results.get("error"):
        return f"Fairness metrics could not be computed for '{_label(feature)}': {results['error']}."

    sp = results.get("Statistical Parity")
    di = results.get("Disparate Impact Ratio")
    if not _is_number(sp) or not _is_number(di):
        return f"Fairness metrics are incomplete for '{_label(feature)}'."

    sp_max = params.get("parity_threshold", STATISTICAL_PARITY_MAX)
    di_min = params.get("impact_threshold", DISPARATE_IMPACT_MIN)
    # Results from before the upper bound existed carry no value for it.
    di_max = params.get("impact_upper_threshold", DISPARATE_IMPACT_MAX)

    subject = (
        f"the combination '{_label(feature)}'" if intersectional else f"'{feature}'"
    )

    probs = {
        k: v for k, v in (results.get("Favorable Probabilities") or {}).items() if _is_number(v)
    }
    groups_sentence = ""
    if len(probs) >= 2:
        high = max(probs, key=probs.get)
        low = min(probs, key=probs.get)
        groups_sentence = (
            f" '{_label(low)}' has the lowest favourable-outcome rate ({probs[low]:.0%}) and "
            f"'{_label(high)}' the highest ({probs[high]:.0%})."
        )

    issues = []
    if not parity_ok(sp, sp_max):
        issues.append(
            f"Statistical Parity is {sp:.2f}, above the limit of {sp_max:.2f}: the "
            f"favourable-outcome rate differs by {sp * 100:.0f} percentage points between groups"
        )
    if not impact_ok(di, di_min, di_max):
        direction = "below" if di < di_min else "above"
        issues.append(
            f"Disparate Impact is {di:.2f}, {direction} the acceptable range of "
            f"{di_min:.2f} to {di_max:.2f}"
        )

    if issues:
        return (
            f"Fairness concerns for {subject}: {'; '.join(issues)}.{groups_sentence} "
            f"Outcomes are not distributed evenly across these groups, which can lead to "
            f"discriminatory decisions."
        )
    return (
        f"{subject[0].upper()}{subject[1:]} passes both fairness checks: Statistical Parity is "
        f"{sp:.2f} (acceptable up to {sp_max:.2f}) and Disparate Impact is {di:.2f} "
        f"(acceptable from {di_min:.2f} to {di_max:.2f}).{groups_sentence}"
    )


def explain(metric, feature, results, params):
    """The explanation for one feature's entry in one analysis section."""
    params = params or {}
    intersectional = metric.startswith("intersectional_")

    if metric == "proxy_identification":
        return _proxy(feature, results, params)
    if metric == "sensitive_predictability":
        return _predictability(feature, results, params)
    if metric.endswith("performance_discrimination"):
        return _performance(feature, results, params, intersectional)
    if metric.endswith("sensitive_representativity"):
        return _representativity(feature, results, params, intersectional)
    if metric.endswith("fairness_metrics"):
        return _fairness(feature, results, params, intersectional)
    return "No explanation is available for this metric."
