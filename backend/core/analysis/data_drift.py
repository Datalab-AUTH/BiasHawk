import pandas as pd
import numpy as np
import argparse
from scipy.stats import ks_2samp, chi2_contingency
from scipy.spatial.distance import jensenshannon

def create_warning(test_name, feature, description, severity, data):
    return {
        "test_name": test_name,
        "feature": feature,
        "description": description,
        "severity": severity,
        "data": data
    }


def perform_drift_analysis(baseline_df, comparison_df):
    """
    Compare two datasets for distribution drift.

    Args:
        baseline_df (pd.DataFrame): the earlier dataset
        comparison_df (pd.DataFrame): the dataset being checked against it

    Returns:
        dict: warnings, metrics and summaries
    """
    analyzer = DriftAnalyzer(baseline_df, comparison_df)
    analyzer.detect_drift()

    warnings = analyzer.get_warnings()
    return {
        "success": True,
        "warnings": warnings,
        "metrics": analyzer.get_metrics(),
        "summary": analyzer.generate_summary(),
        "markdown_summary": analyzer.generate_markdown_summary(),
        "total_warnings": len(warnings),
        "drift_detected": len(warnings) > 0,
    }


class DriftAnalyzer:
    def __init__(self, baseline_df, current_df, significance_level=0.05, bin_count=10):
        self.baseline_df = baseline_df
        self.current_df = current_df
        self.significance_level = significance_level
        self.warnings = []
        self.metrics = []
        self.bin_count = bin_count
        self.drift_checked = False

    def add_warning(self, feature, test_name, description, severity, data):
        warning = create_warning(test_name, feature, description, severity, data)
        self.warnings.append(warning)

    def add_metric(self, feature, test_name, data):
        self.metrics.append({
            "feature": feature,
            "test_name": test_name,
            "data": data
        })

    def detect_drift(self):
        if self.drift_checked:
            return

        common_features = set(self.baseline_df.columns).intersection(self.current_df.columns)

        for feature in common_features:
            base = self.baseline_df[feature].dropna()
            curr = self.current_df[feature].dropna()

            # pandas 3 gives string columns a StringDtype that numpy cannot
            # interpret, so np.issubdtype raises instead of returning False.
            if pd.api.types.is_numeric_dtype(base) and pd.api.types.is_numeric_dtype(curr):
                self._analyze_numeric_feature(feature, base, curr)
            else:
                self._analyze_categorical_feature(feature, base, curr)

        self.drift_checked = True

    def _analyze_numeric_feature(self, feature, base, curr):
        ks_stat, p_value = ks_2samp(base, curr)
        self.add_metric(feature, "Kolmogorov-Smirnov Test", {"ks_stat": ks_stat, "p_value": p_value})
        if p_value < self.significance_level:
            self.add_warning(feature, "Kolmogorov-Smirnov Test",
                             f"Drift detected (p-value={p_value:.5f}).",
                             "high" if ks_stat > 0.5 else "medium",
                             {"ks_stat": ks_stat, "p_value": p_value})

        psi_value = self._calculate_psi(base, curr, self.bin_count)
        self.add_metric(feature, "Population Stability Index", {"psi": psi_value})
        if psi_value > 0.25:
            severity = "high"
        elif psi_value > 0.1:
            severity = "medium"
        else:
            severity = "low"

        if psi_value > 0.1:
            self.add_warning(feature, "Population Stability Index",
                             f"PSI suggests drift (PSI={psi_value:.4f}).", severity,
                             {"psi": psi_value})

        js_div = self._calculate_js_divergence(base, curr, self.bin_count)
        self.add_metric(feature, "Jensen-Shannon Divergence", {"js_divergence": js_div})
        if js_div > 0.1:
            severity = "high" if js_div > 0.25 else "medium"
            self.add_warning(feature, "Jensen-Shannon Divergence",
                             f"JSD suggests drift (JSD={js_div:.4f}).", severity,
                             {"js_divergence": js_div})

    def _analyze_categorical_feature(self, feature, base, curr):
        base_counts = base.value_counts(normalize=True)
        curr_counts = curr.value_counts(normalize=True)
        all_categories = set(base_counts.index).union(curr_counts.index)

        base_freq = np.array([base_counts.get(cat, 0) for cat in all_categories])
        curr_freq = np.array([curr_counts.get(cat, 0) for cat in all_categories])

        chi2_stat, p_value, _, _ = chi2_contingency([base_freq, curr_freq])
        self.add_metric(feature, "Chi-Square Test", {"chi2_stat": chi2_stat, "p_value": p_value})
        if p_value < self.significance_level:
            self.add_warning(feature, "Chi-Square Test",
                             f"Drift detected (p-value={p_value:.5f}).",
                             "medium", {"chi2_stat": chi2_stat, "p_value": p_value})

        js_div = jensenshannon(base_freq, curr_freq)
        self.add_metric(feature, "Jensen-Shannon Divergence", {"js_divergence": js_div})
        if js_div > 0.1:
            severity = "high" if js_div > 0.25 else "medium"
            self.add_warning(feature, "Jensen-Shannon Divergence",
                             f"JSD suggests drift (JSD={js_div:.4f}).", severity,
                             {"js_divergence": js_div})

    def _calculate_psi(self, base, curr, bins=10):
        base_counts, bin_edges = np.histogram(base, bins=bins)
        curr_counts, _ = np.histogram(curr, bins=bin_edges)

        base_perc = base_counts / np.sum(base_counts)
        curr_perc = curr_counts / np.sum(curr_counts)

        base_perc = np.where(base_perc == 0, 1e-6, base_perc)
        curr_perc = np.where(curr_perc == 0, 1e-6, curr_perc)

        psi = np.sum((base_perc - curr_perc) * np.log(base_perc / curr_perc))
        return psi

    def _calculate_js_divergence(self, base, curr, bins=10):
        base_hist, bin_edges = np.histogram(base, bins=bins, density=True)
        curr_hist, _ = np.histogram(curr, bins=bin_edges, density=True)

        base_hist = base_hist / np.sum(base_hist)
        curr_hist = curr_hist / np.sum(curr_hist)

        return jensenshannon(base_hist, curr_hist)

    def get_warnings(self):
        self.detect_drift()
        return self.warnings

    def get_metrics(self):
        self.detect_drift()
        return self.metrics

    def summary(self):
        self.detect_drift()
        if not self.warnings:
            print("No drift detected.")
            return
        print(f"Total warnings: {len(self.warnings)}")
        for w in self.warnings:
            print(f"Feature: {w['feature']}, Test: {w['test_name']}, Severity: {w['severity']}, Description: {w['description']}")

    def generate_summary(self):
        self.detect_drift()
        if not self.warnings:
            return "Drift Analysis Summary:\n- No warnings detected."
        return "Drift Analysis Summary:\n" + "\n".join(
            f"- {w['test_name']} on {w['feature']}: {w['description']} (Severity: {w['severity']})."
            for w in self.warnings)

    def generate_markdown_summary(self):
        self.detect_drift()
        if not self.warnings:
            return "## Drift Analysis Summary\n- **No warnings detected.**"

        lines = ["## Drift Analysis Summary\n", "- **Detected warnings:**"]
        for w in self.warnings:
            lines.append(f"  - **{w['test_name']}** on **{w['feature']}**:")
            lines.append(f"    - **Description:** {w['description']}")
            lines.append(f"    - **Severity:** {w['severity']}")
        return "\n".join(lines)
