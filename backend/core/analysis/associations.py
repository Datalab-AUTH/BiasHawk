"""
Mixed-type association matrix , a drop-in replacement for `dython.nominal.associations`.

dython was a dependency of the old bias-fairness service purely for this one
call, and it hard-depends on matplotlib and seaborn for plotting helpers the
application never used. This is the same three statistics dython computes by
default, so the numbers , and therefore the proxy-identification thresholds
tuned against them , are unchanged:

  numeric  x numeric   -> Pearson correlation
  nominal  x nominal   -> Cramer's V, bias-corrected (Bergsma-Wicher)
  nominal  x numeric   -> correlation ratio (eta)
"""

import numpy as np
import pandas as pd
from scipy import stats


def cramers_v(x, y):
    """Bias-corrected Cramer's V, matching dython's default `nom_nom_assoc`."""
    confusion = pd.crosstab(x, y)
    if confusion.size == 0 or confusion.shape[0] < 2 or confusion.shape[1] < 2:
        return 0.0

    chi2 = stats.chi2_contingency(confusion, correction=False)[0]
    n = confusion.to_numpy().sum()
    if n == 0:
        return 0.0

    phi2 = chi2 / n
    r, k = confusion.shape
    # Bergsma-Wicher correction: subtract the expected value of phi2 under
    # independence, then shrink the table dimensions to match.
    phi2corr = max(0.0, phi2 - ((k - 1) * (r - 1)) / (n - 1))
    rcorr = r - ((r - 1) ** 2) / (n - 1)
    kcorr = k - ((k - 1) ** 2) / (n - 1)
    denominator = min(kcorr - 1, rcorr - 1)
    if denominator <= 0:
        return 0.0
    return float(np.sqrt(phi2corr / denominator))


def correlation_ratio(categories, measurements):
    """Eta: how much of a numeric variable's variance a category explains."""
    frame = pd.DataFrame({"cat": categories, "num": measurements}).dropna()
    if frame.empty:
        return 0.0

    values = frame["num"].to_numpy(dtype=float)
    total_mean = values.mean()
    total_variance = ((values - total_mean) ** 2).sum()
    if total_variance == 0:
        return 0.0

    between = 0.0
    for _, group in frame.groupby("cat", observed=True)["num"]:
        group_values = group.to_numpy(dtype=float)
        between += len(group_values) * (group_values.mean() - total_mean) ** 2

    return float(np.sqrt(between / total_variance))


def _pearson(x, y):
    frame = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(frame) < 2:
        return 0.0
    if frame["x"].nunique() < 2 or frame["y"].nunique() < 2:
        return 0.0
    value = frame["x"].corr(frame["y"])
    return 0.0 if pd.isna(value) else float(value)


def associations(df, nominal_columns=None, nan_strategy="drop_samples", **_ignored):
    """
    Association matrix for a frame of mixed nominal and numeric columns.

    Returns {"corr": DataFrame} , the same shape the caller expects from dython,
    so call sites are unchanged. Extra keyword arguments dython accepted (plot,
    compute_only, mark_columns) are accepted and ignored.
    """
    nominal_columns = set(nominal_columns or [])

    if nan_strategy == "drop_samples":
        df = df.dropna(axis=0)
    elif nan_strategy == "drop_features":
        df = df.dropna(axis=1)

    columns = list(df.columns)
    matrix = pd.DataFrame(np.eye(len(columns)), index=columns, columns=columns, dtype=float)

    for i, left in enumerate(columns):
        for right in columns[i + 1 :]:
            left_nominal = left in nominal_columns
            right_nominal = right in nominal_columns

            if left_nominal and right_nominal:
                value = cramers_v(df[left], df[right])
            elif not left_nominal and not right_nominal:
                value = _pearson(df[left], df[right])
            elif left_nominal:
                value = correlation_ratio(df[left], df[right])
            else:
                value = correlation_ratio(df[right], df[left])

            matrix.loc[left, right] = value
            matrix.loc[right, left] = value

    return {"corr": matrix}
