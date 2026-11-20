import json
import argparse
import sys

from core.analysis.thresholds import impact_ok

# The BiasDriftAnalyzer class remains unchanged as its logic is self-contained.
# --- START of BiasDriftAnalyzer Class ---
class BiasDriftAnalyzer:
    """
    Analyzes bias drift by comparing a baseline and current bias metrics dictionary.

    This class identifies significant negative changes in fairness and performance
    metrics between two points in time.
    """

    def __init__(self, baseline_report_dict, current_report_dict):
        """
        Initializes the analyzer with baseline and current metrics.

        Args:
            baseline_report_dict (dict): The dictionary of bias metrics from the baseline dataset.
            current_report_dict (dict): The dictionary of bias metrics from the current dataset.
        """
        self.baseline = baseline_report_dict
        self.current = current_report_dict
        self.drift_events = []

        # --- Configurable Thresholds for Drift Detection ---
        self.PERFORMANCE_DISPARITY_DRIFT_THRESHOLD = 0.10  # Worsens if disparity increases by > 10% (0.1)
        self.STATISTICAL_PARITY_DRIFT_THRESHOLD = 0.10  # Worsens if parity increases by > 10% (0.1)
        self.DISPARATE_IMPACT_DRIFT_THRESHOLD = -0.10  # Worsens if DI moves away from 1.0 by > 10% (0.1)
        self.PREDICTABILITY_DRIFT_THRESHOLD = 0.05  # Flag if predictability increases by > 5% (0.05)

    def analyze(self):
        """
        Runs all bias drift checks and populates the drift_events list.
        """
        self._check_performance_drift("performance_discrimination")
        self._check_performance_drift("intersectional_performance_discrimination")
        self._check_fairness_drift("fairness_metrics")
        self._check_fairness_drift("intersectional_fairness_metrics")
        self._check_predictability_drift("sensitive_predictability")

        # Sort events by severity for clearer reporting
        self.drift_events.sort(
            key=lambda x: ("high", "medium", "low").index(x.get("severity", "low"))
        )

    def get_results_dict(self):
        """
        Returns the analysis results as a dictionary.

        Returns:
            dict: A dictionary containing a list of all detected drift events.
        """
        if not self.drift_events:
            self.analyze()
        return {"bias_drift_analysis": self.drift_events}

    def generate_markdown_report(self):
        """
        Generates a human-readable Markdown report from the analysis results.

        Returns:
            str: A formatted Markdown string summarizing the bias drift.
        """
        if not self.drift_events:
            self.analyze()

        if not self.drift_events:
            return "## Bias Drift Analysis Summary\n- **No significant bias drift detected.** All checked metrics are within acceptable drift thresholds."

        lines = ["## Bias Drift Analysis Summary"]
        lines.append(
            "\n_Bias drift is identified when fairness or performance disparity metrics degrade over time. The following issues were detected by comparing the baseline and current reports._\n")

        for event in self.drift_events:
            lines.append(f"### {event['type']} (Severity: {event['severity'].upper()})")
            lines.append(f"- **Feature Group:** `{event['feature']}`")
            lines.append(f"- **Metric:** `{event['metric']}`")
            lines.append(f"- **Description:** {event['description']}")
            lines.append(f"- **Change Details:**")
            lines.append(f"  - Baseline Value: `{event['baseline_value']:.3f}`")
            lines.append(f"  - Current Value:  `{event['current_value']:.3f}`")
            lines.append(f"  - **Change:** `{event['change']:+.3f}`")
            lines.append("")

        return "\n".join(lines)

    def _add_drift_event(self, event_type, metric, feature, description, baseline_val, current_val, severity):
        self.drift_events.append({
            "type": event_type,
            "metric": metric,
            "feature": feature,
            "description": description,
            "baseline_value": float(baseline_val),
            "current_value": float(current_val),
            "change": float(current_val - baseline_val),
            "severity": severity
        })

    def _calculate_disparity(self, scores_dict):
        """Calculates max-min disparity from a dictionary of scores."""
        if not scores_dict or not isinstance(scores_dict, dict):
            return None

        valid_scores = [v for v in scores_dict.values() if isinstance(v, (int, float))]
        if len(valid_scores) < 2:
            return None

        return max(valid_scores) - min(valid_scores)

    def _check_performance_drift(self, section_name):
        baseline_section = self.baseline.get(section_name, {}).get("results", {})
        current_section = self.current.get(section_name, {}).get("results", {})

        for feature, baseline_scores in baseline_section.items():
            current_scores = current_section.get(feature)
            if not current_scores:
                continue

            b_disp = self._calculate_disparity(baseline_scores)
            c_disp = self._calculate_disparity(current_scores)

            if b_disp is not None and c_disp is not None:
                delta = c_disp - b_disp
                if delta > self.PERFORMANCE_DISPARITY_DRIFT_THRESHOLD:
                    self._add_drift_event(
                        event_type="Performance Disparity Worsened",
                        metric="F1-Score Disparity",
                        feature=feature,
                        description="The performance gap (max-min F1 score) between subgroups has widened.",
                        baseline_val=b_disp,
                        current_val=c_disp,
                        severity="high" if delta > 0.2 else "medium"
                    )

    def _check_fairness_drift(self, section_name):
        baseline_section = self.baseline.get(section_name, {}).get("results", {})
        current_section = self.current.get(section_name, {}).get("results", {})

        for feature, baseline_metrics in baseline_section.items():
            current_metrics = current_section.get(feature)
            if not current_metrics:
                continue

            # Check Statistical Parity (higher is worse)
            b_sp = baseline_metrics.get('Statistical Parity')
            c_sp = current_metrics.get('Statistical Parity')
            if b_sp is not None and c_sp is not None:
                delta = float(c_sp) - float(b_sp)
                if delta > self.STATISTICAL_PARITY_DRIFT_THRESHOLD:
                    self._add_drift_event(
                        event_type="Fairness Metric Degraded",
                        metric="Statistical Parity",
                        feature=feature,
                        description="The difference in the rate of favorable outcomes between subgroups has increased.",
                        baseline_val=b_sp,
                        current_val=c_sp,
                        severity="high" if delta > 0.2 else "medium"
                    )

            # Check Disparate Impact (closer to 1.0 is better)
            b_di = baseline_metrics.get('Disparate Impact Ratio')
            c_di = current_metrics.get('Disparate Impact Ratio')
            if b_di is not None and c_di is not None:
                delta = float(c_di) - float(b_di)
                # We care most when the value moves away from 1.0
                if abs(1.0 - c_di) > abs(1.0 - b_di) and abs(delta) > abs(self.DISPARATE_IMPACT_DRIFT_THRESHOLD):
                    self._add_drift_event(
                        event_type="Fairness Metric Degraded",
                        metric="Disparate Impact Ratio",
                        feature=feature,
                        description="The ratio of favorable outcomes has moved further away from parity (1.0).",
                        baseline_val=b_di,
                        current_val=c_di,
                        # High when it has just left the acceptable range.
                        severity="high" if not impact_ok(c_di) and impact_ok(b_di) else "medium"
                    )

    def _check_predictability_drift(self, section_name):
        baseline_section = self.baseline.get(section_name, {}).get("results", {})
        current_section = self.current.get(section_name, {}).get("results", {})

        for feature, b_pred in baseline_section.items():
            c_pred = current_section.get(feature)
            if b_pred is not None and c_pred is not None:
                delta = c_pred - b_pred
                if delta > self.PREDICTABILITY_DRIFT_THRESHOLD:
                    self._add_drift_event(
                        event_type="Proxy Warning",
                        metric="Sensitive Predictability",
                        feature=feature,
                        description="The model is now better at predicting this sensitive attribute, increasing the risk of it being used as a proxy.",
                        baseline_val=b_pred,
                        current_val=c_pred,
                        severity="medium"
                    )
# --- END of BiasDriftAnalyzer Class ---



def perform_bias_drift_analysis(baseline_bias_dict, current_bias_dict):
    """
    Perform bias drift analysis between two bias report dictionaries.

    Args:
        baseline_bias_dict (dict): The baseline bias analysis results
        current_bias_dict (dict): The current bias analysis results

    Returns:
        dict: Analysis results containing drift events, summary, and markdown report
    """
    try:
        # Create bias drift analyzer instance
        analyzer = BiasDriftAnalyzer(baseline_bias_dict, current_bias_dict)

        # Perform analysis
        analyzer.analyze()

        # Get results
        results_dict = analyzer.get_results_dict()
        markdown_report = analyzer.generate_markdown_report()

        return {
            "success": True,
            "drift_events": results_dict.get("bias_drift_analysis", []),
            "total_drift_events": len(results_dict.get("bias_drift_analysis", [])),
            "bias_drift_detected": len(results_dict.get("bias_drift_analysis", [])) > 0,
            "markdown_report": markdown_report,
            "results_dict": results_dict
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Bias drift analysis failed: {str(e)}"
        }


