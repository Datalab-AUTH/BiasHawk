from typing import Dict, Any
from core.risk.base import BaseAgent


class NISTMapperAgent(BaseAgent):
    """Maps findings to NIST AI RMF categories."""

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Map all findings to NIST framework."""

        quality_analysis = state.get("quality_analysis", {})
        bias_analysis = state.get("bias_analysis", {})
        drift_analysis = state.get("drift_analysis", {})
        governance_analysis = state.get("governance_analysis", {})

        nist_mapping = {
            "GOVERN": self._map_govern(governance_analysis),
            "MAP": self._map_map(quality_analysis, bias_analysis, drift_analysis),
            "MEASURE": self._map_measure(quality_analysis, bias_analysis, drift_analysis),
            "MANAGE": self._map_manage(quality_analysis, bias_analysis, drift_analysis)
        }

        state["nist_mapping"] = nist_mapping
        return state

    def _map_govern(self, governance_analysis: Dict) -> Dict[str, Any]:
        """Map to GOVERN function."""

        return {
            "governance_score": governance_analysis.get("percentage", 0),
            "findings": governance_analysis.get("findings", []),
            "risk_level": governance_analysis.get("severity", "UNKNOWN"),
            "nist_subcategories": ["GOVERN-1.1", "GOVERN-1.2", "GOVERN-4.1"]
        }

    def _map_map(self, quality_analysis: Dict, bias_analysis: Dict, drift_analysis: Dict) -> Dict[str, Any]:
        """Map to MAP function."""

        risk_categories = {}

        # MAP 2.2.4: Data Privacy
        risk_categories["MAP-2.2.4-Data-Privacy"] = {
            "risk_level": "MEDIUM",
            "findings": ["Assessment based on governance data"]
        }

        # MAP 2.2.6: Harmful Bias
        bias_findings = bias_analysis.get("findings", [])
        bias_severity = bias_analysis.get("severity", "LOW")

        risk_categories["MAP-2.2.6-Harmful-Bias"] = {
            "risk_level": bias_severity,
            "findings": [
                f"{f['attribute']}: DIR={f['disparate_impact_ratio']:.2f} ({'FAIL' if not f['passes_80_rule'] else 'PASS'})"
                for f in bias_findings[:5]
            ]
        }

        # MAP 2.2.9: Information Security
        risk_categories["MAP-2.2.9-Information-Security"] = {
            "risk_level": quality_analysis.get("severity", "MEDIUM"),
            "findings": quality_analysis.get("issues", [])
        }

        return {
            "risk_categories": risk_categories,
            "overall_map_risk": bias_severity
        }

    def _map_measure(self, quality_analysis: Dict, bias_analysis: Dict, drift_analysis: Dict) -> Dict[str, Any]:
        """Map to MEASURE function."""

        return {
            "data_quality_metrics": {
                "duplicate_percentage": quality_analysis.get("duplicate_percentage", 0),
                "outlier_features": len(quality_analysis.get("outlier_features", [])),
                "missing_data_features": len(quality_analysis.get("missing_data_features", []))
            },
            "bias_metrics": {
                "attributes_assessed": len(bias_analysis.get("findings", [])),
                "failing_80_rule": bias_analysis.get("failing_80_rule", 0)
            },
            "drift_metrics": {
                "features_with_drift": drift_analysis.get("drift_count", 0),
                "bias_drift_events": drift_analysis.get("bias_drift_count", 0)
            }
        }

    def _map_manage(self, quality_analysis: Dict, bias_analysis: Dict, drift_analysis: Dict) -> Dict[str, Any]:
        """Map to MANAGE function."""

        return {
            "quality_severity": quality_analysis.get("severity", "LOW"),
            "bias_severity": bias_analysis.get("severity", "LOW"),
            "drift_severity": drift_analysis.get("severity", "LOW")
        }
