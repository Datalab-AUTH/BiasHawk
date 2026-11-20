"""
Data quality checks.

Ported from the old `data-quality` service's Data_Quality.py. Pure pandas: it
takes a DataFrame and returns plain Python structures. No HTTP, no database, no
message queue , the old version downloaded its CSV over HTTP from
BACKEND_MEDIA_URL and validated that the URL started with "http".
"""

import logging

import numpy as np
import pandas as pd

log = logging.getLogger("core.analysis.quality")

MISSING_THRESHOLD = 0.1
OUTLIER_Z_THRESHOLD = 3.0
LOW_VARIABILITY_THRESHOLD = 0.01

# Type consistency is O(rows); sample beyond this rather than scanning everything.
TYPE_CHECK_SAMPLE = 5000


def _warning(test_name, feature, description, severity, data=None):
    return {
        "test_name": test_name,
        "feature": feature or "Dataset",
        "description": description,
        "severity": severity,
        "data": data or {},
    }


def _z_score_outliers(series, threshold):
    """Count of values more than `threshold` standard deviations from the mean."""
    values = series.dropna()
    if values.empty:
        return 0, 0.0
    std = values.std()
    if not std or np.isnan(std):
        return 0, 0.0
    z_scores = np.abs((values - values.mean()) / std)
    count = int((z_scores > threshold).sum())
    return count, (count / len(values) if len(values) else 0.0)


def find_warnings(
    df,
    missing_threshold=MISSING_THRESHOLD,
    outlier_threshold=OUTLIER_Z_THRESHOLD,
    low_variability_threshold=LOW_VARIABILITY_THRESHOLD,
):
    """Every quality issue found in the frame, as a list of warning dicts."""
    warnings = []
    if df.empty:
        return warnings

    # --- missing data ---
    for feature, pct in df.isnull().mean().items():
        if pct > missing_threshold:
            warnings.append(
                _warning(
                    "Missing Data",
                    feature,
                    f"Feature has {pct:.2%} missing values (threshold: {missing_threshold:.0%}).",
                    "high" if pct > missing_threshold * 2 else "medium",
                    {"missing_percentage": float(pct), "threshold": missing_threshold},
                )
            )

    # --- outliers ---
    for feature in df.select_dtypes(include=np.number).columns:
        count, pct = _z_score_outliers(df[feature], outlier_threshold)
        if count:
            warnings.append(
                _warning(
                    "Outlier Detection",
                    feature,
                    f"Feature has {count} potential outliers based on "
                    f"Z-score > {outlier_threshold}.",
                    "medium" if pct < 0.05 else "high",
                    {
                        "outlier_count": count,
                        "outlier_percentage": pct,
                        "threshold": outlier_threshold,
                    },
                )
            )

    # --- constant and low-variability columns ---
    for feature in df.columns:
        non_na = int(df[feature].count())
        if non_na == 0:
            continue
        unique = int(df[feature].nunique())
        if unique == 1:
            value = df[feature].dropna().unique()[0]
            warnings.append(
                _warning(
                    "Constant Value",
                    feature,
                    f"Feature contains only a single value ('{value}') across all non-missing entries.",
                    "medium",
                    {"unique_count": unique, "value": value},
                )
            )
        else:
            ratio = unique / non_na
            if ratio < low_variability_threshold:
                warnings.append(
                    _warning(
                        "Low Variability",
                        feature,
                        f"Feature has low unique value ratio "
                        f"({ratio:.2%}, {unique} unique / {non_na} non-NA values).",
                        "low",
                        {"unique_ratio": ratio, "unique_count": unique, "non_na_count": non_na},
                    )
                )

    # --- duplicate rows ---
    duplicates = int(df.duplicated().sum())
    if duplicates:
        pct = duplicates / len(df)
        warnings.append(
            _warning(
                "Duplicate Rows",
                None,
                f"Dataset contains {duplicates} ({pct:.2%}) complete duplicate rows.",
                "medium" if pct < 0.1 else "high",
                {"duplicate_count": duplicates, "duplicate_percentage": pct},
            )
        )

    # --- mixed python types within a column ---
    sample = df.sample(TYPE_CHECK_SAMPLE, random_state=0) if len(df) > TYPE_CHECK_SAMPLE else df
    for feature in sample.columns:
        try:
            types = sample[feature].dropna().map(type).unique()
        except Exception as exc:  # a column of unhashable values, say
            log.debug("Type consistency check skipped for %r: %s", feature, exc)
            continue
        if len(types) > 1:
            names = ", ".join(t.__name__ for t in types)
            warnings.append(
                _warning(
                    "Mixed Data Types",
                    feature,
                    f"Feature potentially contains mixed data types (detected: {names}).",
                    "medium",
                    {"unique_types_detected": len(types), "example_types": names},
                )
            )

    return warnings


def summarise_metrics(df, outlier_threshold=OUTLIER_Z_THRESHOLD):
    """
    Per-feature quality metrics, as a DataFrame indexed by column name.

    The old service closed this table with a "Dataset Level" row carrying the
    duplicate count and the shape, and wrote a dash wherever a metric did not
    apply. Both are kept: this table is what the model is shown, so dropping
    them would change what the report can say.
    """
    if df.empty:
        return pd.DataFrame()

    numeric = df.select_dtypes(include=np.number)

    outlier_counts = {
        feature: _z_score_outliers(df[feature], outlier_threshold)[0]
        for feature in numeric.columns
    }
    unique_ratios = {
        feature: (df[feature].nunique() / count * 100 if (count := int(df[feature].count())) else np.nan)
        for feature in df.columns
    }
    type_counts = {feature: int(df[feature].dropna().map(type).nunique()) for feature in df.columns}

    summary = pd.DataFrame(
        {
            "Missing Data (%)": df.isnull().mean() * 100,
            "Outlier Count (Z-score)": pd.Series(outlier_counts),
            "Unique Value Ratio (%)": pd.Series(unique_ratios),
            "Unique Data Types Count": pd.Series(type_counts),
            "Mean": numeric.mean(),
            "Std Dev": numeric.std(),
            "Min": numeric.min(),
            "Max": numeric.max(),
        }
    )

    summary.loc["Dataset Level", "Duplicate Row Count"] = int(df.duplicated().sum())
    summary.loc["Dataset Level", "Total Rows"] = int(len(df))
    summary.loc["Dataset Level", "Total Columns"] = int(len(df.columns))

    # A dash reads better than NaN for a metric that does not apply to a
    # column, e.g. a mean for a text feature.
    return summary.fillna("-").round(2)


def dataset_totals(df):
    """Whole-dataset figures, kept out of the per-feature table."""
    return {
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "duplicate_rows": int(df.duplicated().sum()) if not df.empty else 0,
    }


def _json_safe(value):
    """numpy scalars and NaN are not JSON-serialisable; JSONField needs them to be."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if value is pd.NaT or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def analyse(df, **thresholds):
    """
    Run every check and return results ready to store on an Instance.

    Returns (metrics, warnings, metrics_frame, warnings_frame) , the frames are
    for the LLM prompt, the plain structures are for the database.
    """
    warnings = find_warnings(df, **thresholds)
    metrics_frame = summarise_metrics(
        df, outlier_threshold=thresholds.get("outlier_threshold", OUTLIER_Z_THRESHOLD)
    )

    metrics = {
        "features": _json_safe(metrics_frame.to_dict("index")),
        "dataset": dataset_totals(df),
    }
    warnings_frame = pd.DataFrame(warnings) if warnings else pd.DataFrame()
    return metrics, _json_safe(warnings), metrics_frame, warnings_frame
