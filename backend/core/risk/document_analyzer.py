from typing import Dict, Any
from core.analysis.thresholds import impact_ok, parity_ok
from core.risk.base import BaseAgent


class DocumentAnalyzerAgent(BaseAgent):
    """Analyzes input reports with proper error handling."""

    def __init__(self, report_type: str):
        # The knowledge base is no longer injected: NIST guidance is retrieved
        # from pgvector through BaseAgent, not from a per-agent ChromaDB handle.
        self.report_type = report_type

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and structure findings from raw metrics."""

        print(f"\n[{self.report_type.upper()}] Starting analysis...")

        try:
            if self.report_type == "quality":
                return self._analyze_quality_metrics(state)
            elif self.report_type == "bias":
                return self._analyze_bias_metrics(state)
            elif self.report_type == "drift":
                return self._analyze_drift_metrics(state)
            elif self.report_type == "governance":
                return self._analyze_governance(state)
        except Exception as e:
            print(f"  ❌ ERROR in {self.report_type}: {e}")
            import traceback
            traceback.print_exc()

        return state

    def _analyze_quality_metrics(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze data quality metrics directly."""

        input_data = state.get("input_data", {})
        quality_metrics = input_data.get("data_quality_metrics", {})

        if not quality_metrics:
            print("  ⚠️  No quality metrics found!")
            state["quality_analysis"] = {
                "severity": "UNKNOWN",
                "duplicate_percentage": 0,
                "duplicate_rows": 0,
                "total_rows": 0,
                "outlier_features": [],
                "missing_data_features": [],
                "issues": []
            }
            return state

        # Extract dataset-level metrics
        dataset_metrics = quality_metrics.get("Dataset Level", {})
        total_rows = dataset_metrics.get("Total Rows", 1) or 1
        duplicate_rows = dataset_metrics.get("Duplicate Row Count", 0) or 0
        duplicate_pct = (duplicate_rows / total_rows * 100) if total_rows > 1 else 0

        print(f"  Found: {total_rows:,} rows, {duplicate_rows} duplicates ({duplicate_pct:.1f}%)")

        # Count features with issues
        outlier_features = []
        missing_data_features = []

        for feature, metrics in quality_metrics.items():
            if feature != "Dataset Level" and isinstance(metrics, dict):
                outliers = metrics.get("Outlier Count (Z-score)")
                if outliers and outliers != "-":
                    try:
                        outlier_count = int(float(outliers))
                        if outlier_count > 0:
                            outlier_features.append({
                                "feature": feature,
                                "count": outlier_count
                            })
                    except:
                        pass

                missing_pct = metrics.get("Missing Data (%)")
                if missing_pct and missing_pct != "-":
                    try:
                        missing_val = float(missing_pct)
                        if missing_val > 0:
                            missing_data_features.append({
                                "feature": feature,
                                "percentage": missing_val
                            })
                    except:
                        pass

        print(f"  Outliers in {len(outlier_features)} features")

        # Determine severity
        if duplicate_pct > 20 or len(missing_data_features) > 5:
            severity = "CRITICAL"
        elif duplicate_pct > 15 or len(missing_data_features) > 3:
            severity = "HIGH"
        elif duplicate_pct > 5 or len(outlier_features) > 3:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        print(f"  ✓ Quality severity: {severity}")

        state["quality_analysis"] = {
            "severity": severity,
            "duplicate_percentage": duplicate_pct,
            "duplicate_rows": duplicate_rows,
            "total_rows": total_rows,
            "outlier_features": outlier_features,
            "missing_data_features": missing_data_features,
            "issues": [
                f"Duplicates: {duplicate_pct:.1f}%",
                f"Outliers in {len(outlier_features)} features",
                f"Missing data in {len(missing_data_features)} features"
            ]
        }

        return state

    def _analyze_bias_metrics(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze bias assessment metrics directly."""

        input_data = state.get("input_data", {})
        bias_results = input_data.get("bias_assessment_results", {})

        if not bias_results:
            print("  ⚠️  No bias results found!")
            state["bias_analysis"] = {
                "severity": "UNKNOWN",
                "findings": [],
                "critical_count": 0,
                "high_count": 0,
                "failing_80_rule": 0
            }
            return state

        fairness_metrics = bias_results.get("fairness_metrics", {}).get("results", {})
        print(f"  Analyzing {len(fairness_metrics)} protected attributes...")

        findings = []
        critical_count = 0
        high_count = 0

        for attribute, metrics in fairness_metrics.items():
            dir_ratio = metrics.get("Disparate Impact Ratio", 1.0)
            stat_parity = metrics.get("Statistical Parity", 0.0)
            fav_probs = metrics.get("Favorable Probabilities", {})

            if dir_ratio < 0.5:
                severity = "CRITICAL"
                critical_count += 1
            elif not impact_ok(dir_ratio):
                severity = "HIGH"
                high_count += 1
            elif not parity_ok(stat_parity):
                severity = "MEDIUM"
            else:
                severity = "LOW"

            print(f"    {attribute}: DIR={dir_ratio:.2f}, severity={severity}")

            findings.append({
                "attribute": attribute,
                "disparate_impact_ratio": dir_ratio,
                "statistical_parity": stat_parity,
                "favorable_probabilities": fav_probs,
                "severity": severity,
                "passes_80_rule": impact_ok(dir_ratio)
            })

        if critical_count > 0:
            overall_severity = "CRITICAL"
        elif high_count > 0:
            overall_severity = "HIGH"
        elif findings:
            overall_severity = "MEDIUM"
        else:
            overall_severity = "LOW"

        print(f"  ✓ Bias severity: {overall_severity}")

        state["bias_analysis"] = {
            "severity": overall_severity,
            "findings": findings,
            "critical_count": critical_count,
            "high_count": high_count,
            "failing_80_rule": sum(1 for f in findings if not f["passes_80_rule"])
        }

        return state

    def _analyze_drift_metrics(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze drift metrics directly."""

        input_data = state.get("input_data", {})
        drift_metrics = input_data.get("drift_metrics", [])
        bias_drift = input_data.get("bias_drift_events", [])

        print(f"  Drift metrics: {len(drift_metrics)} entries")
        print(f"  Bias drift events: {len(bias_drift)} events")

        if not drift_metrics and not bias_drift:
            state["drift_analysis"] = {
                "severity": "NONE",
                "drift_detected": [],
                "bias_drift_events": [],
                "drift_count": 0,
                "bias_drift_count": 0
            }
            return state

        drift_detected = []

        for metric in drift_metrics:
            test_name = metric.get("test_name", "")
            feature = metric.get("feature", "")
            data = metric.get("data", {})

            if test_name == "Kolmogorov-Smirnov Test":
                p_value = data.get("p_value", 1.0)
                if p_value < 0.05:
                    drift_detected.append({
                        "feature": feature,
                        "test": "KS Test",
                        "p_value": p_value,
                        "severity": "HIGH" if p_value < 0.01 else "MEDIUM"
                    })

            elif test_name == "Jensen-Shannon Divergence":
                jsd = data.get("js_divergence", 0.0)
                if jsd > 0.15:
                    drift_detected.append({
                        "feature": feature,
                        "test": "JSD",
                        "jsd": jsd,
                        "severity": "MEDIUM"
                    })

        has_bias_drift = len(bias_drift) > 0
        has_data_drift = len(drift_detected) > 0

        if has_bias_drift and has_data_drift:
            severity = "CRITICAL"
        elif has_bias_drift:
            severity = "HIGH"
        elif len(drift_detected) > 2:
            severity = "HIGH"
        elif len(drift_detected) > 0:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        print(f"  ✓ Drift severity: {severity}")

        state["drift_analysis"] = {
            "severity": severity,
            "drift_detected": drift_detected,
            "bias_drift_events": bias_drift,
            "drift_count": len(drift_detected),
            "bias_drift_count": len(bias_drift)
        }

        return state

    def _analyze_governance(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze governance documentation - handle dicts."""

        input_data = state.get("input_data", {})
        system_doc = input_data.get("ai_system_documentation")
        data_compliance = input_data.get("data_compliance_form")

        print(f"  System doc available: {system_doc is not None}")
        print(f"  Compliance form available: {data_compliance is not None}")

        if not system_doc and not data_compliance:
            state["governance_analysis"] = {
                "score": 0,
                "max_score": 0,
                "percentage": 0,
                "severity": "UNKNOWN",
                "findings": []
            }
            return state

        score = 0
        max_score = 0
        findings = []

        if system_doc:
            print("  Analyzing system documentation...")

            human_oversight = system_doc.get("human_oversight", {})
            logging_doc = system_doc.get("logging_and_documentation", {})
            gdpr_assessment = system_doc.get("gdpr_conformity_assessment", {})

            if human_oversight.get("human_in_the_loop", False):
                score += 20
                findings.append("✓ Human-in-the-loop oversight")
            else:
                findings.append("✗ No human-in-the-loop oversight")
            max_score += 20

            if logging_doc.get("logs_maintained", False):
                score += 15
                findings.append("✓ Audit logs maintained")
            else:
                findings.append("✗ Audit logs not maintained")
            max_score += 15

            if gdpr_assessment.get("assessment_performed", False):
                score += 15
                findings.append("✓ GDPR assessment performed")
            else:
                findings.append("✗ GDPR assessment not performed")
            max_score += 15

        if data_compliance:
            print("  Analyzing data compliance...")

            collection_origin = data_compliance.get("Data_Collection_and_Origin", {})
            management_gov = data_compliance.get("Data_Management_and_Governance", {})

            if collection_origin.get("Consent_Mechanism_Documented", False):
                score += 10
                findings.append("✓ Consent mechanism documented")
            else:
                findings.append("✗ Consent not documented")
            max_score += 10

            if management_gov.get("Data_Lineage_and_Provenance_Tracking", False):
                score += 10
                findings.append("✓ Data lineage tracked")
            else:
                findings.append("✗ Data lineage not tracked")
            max_score += 10

            if management_gov.get("Compliance_with_GDPR", False):
                score += 15
                findings.append("✓ GDPR compliant")
            else:
                findings.append("✗ Not GDPR compliant")
            max_score += 15

            if collection_origin.get("Anonymization_or_Pseudonymization_Applied", False):
                score += 15
                findings.append("✓ Anonymization applied")
            else:
                findings.append("✗ No anonymization")
            max_score += 15

        percentage = (score / max_score * 100) if max_score > 0 else 0
        severity = "LOW" if percentage > 80 else "MEDIUM" if percentage > 60 else "HIGH"

        print(f"  ✓ Governance score: {score}/{max_score} ({percentage:.1f}%), severity={severity}")

        state["governance_analysis"] = {
            "score": score,
            "max_score": max_score,
            "percentage": percentage,
            "severity": severity,
            "findings": findings
        }

        return state
