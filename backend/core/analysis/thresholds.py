"""
Pass/fail rules for the group fairness metrics.

One place for them, so the assessment's warnings, the per-metric
explanations, the drift checks and the risk analysis all judge a number the
same way.

- Statistical Parity is the gap between the highest and lowest favourable
  outcome rate across groups. Up to 0.10 is acceptable; above it is a problem.
- Disparate Impact is the ratio of those rates. It is acceptable from 0.80 to
  1.25 inclusive (the four-fifths rule and its reciprocal) and a problem
  outside that range.
"""

STATISTICAL_PARITY_MAX = 0.10
DISPARATE_IMPACT_MIN = 0.80
DISPARATE_IMPACT_MAX = 1.25


def parity_ok(value, threshold=STATISTICAL_PARITY_MAX):
    """True when a Statistical Parity difference is within the acceptable gap."""
    return float(value) <= float(threshold)


def impact_ok(value, lower=DISPARATE_IMPACT_MIN, upper=DISPARATE_IMPACT_MAX):
    """True when a Disparate Impact ratio lies inside the acceptable range."""
    return float(lower) <= float(value) <= float(upper)
