from typing import Dict, Any, List
from core.risk.base import BaseAgent
from core.risk.schemas import PrioritizedAction


class RiskPrioritizerAgent(BaseAgent):
    """Prioritizes risks and generates actions."""

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Prioritize all identified risks."""

        nist_mapping = state.get("nist_mapping", {})

        all_risks = self._collect_risks(nist_mapping, state)
        prioritized_risks = self._prioritize_risks(all_risks)
        prioritized_actions = self._generate_actions(prioritized_risks, state)

        state["prioritized_actions"] = prioritized_actions
        state["risk_summary"] = {
            "critical_count": sum(1 for r in prioritized_risks if r["severity"] == "CRITICAL"),
            "high_count": sum(1 for r in prioritized_risks if r["severity"] == "HIGH"),
            "medium_count": sum(1 for r in prioritized_risks if r["severity"] == "MEDIUM"),
            "low_count": sum(1 for r in prioritized_risks if r["severity"] == "LOW")
        }

        return state

    def _collect_risks(self, nist_mapping: Dict, state: Dict) -> List[Dict]:
        """Collect all risks."""

        risks = []

        # MAP risks
        map_section = nist_mapping.get("MAP", {})
        for category, data in map_section.get("risk_categories", {}).items():
            risks.append({
                "nist_category": category,
                "severity": data["risk_level"],
                "findings": data["findings"],
                "function": "MAP"
            })

        # GOVERN risks
        govern_section = nist_mapping.get("GOVERN", {})
        if govern_section.get("risk_level") in ["HIGH", "CRITICAL"]:
            risks.append({
                "nist_category": "GOVERN",
                "severity": govern_section["risk_level"],
                "findings": govern_section.get("findings", []),
                "function": "GOVERN"
            })

        # MEASURE/MANAGE (drift)
        drift_analysis = state.get("drift_analysis", {})
        if drift_analysis.get("severity") in ["HIGH", "CRITICAL"]:
            risks.append({
                "nist_category": "MEASURE-3.3-Drift",
                "severity": drift_analysis["severity"],
                "findings": [f"{drift_analysis['drift_count']} features with drift"],
                "function": "MEASURE"
            })

        return risks

    def _prioritize_risks(self, risks: List[Dict]) -> List[Dict]:
        """Score and sort risks."""

        severity_scores = {
            "CRITICAL": 100,
            "HIGH": 75,
            "MEDIUM": 50,
            "LOW": 25,
            "UNKNOWN": 0
        }

        for risk in risks:
            risk["score"] = severity_scores.get(risk["severity"], 0)

        return sorted(risks, key=lambda x: x["score"], reverse=True)

    def _generate_actions(self, prioritized_risks: List[Dict], state: Dict) -> List[PrioritizedAction]:
        """Generate specific actions."""

        actions = []
        priority = 1

        for risk in prioritized_risks:
            if risk["severity"] in ["CRITICAL", "HIGH"]:

                if "Bias" in risk["nist_category"]:
                    bias_analysis = state.get("bias_analysis", {})
                    failing_attrs = [
                        f['attribute'] for f in bias_analysis.get("findings", [])
                        if not f.get("passes_80_rule", True)
                    ]

                    action = PrioritizedAction(
                        priority=priority,
                        risk_category=risk["nist_category"],
                        risk_description=f"Harmful bias in: {', '.join(failing_attrs[:3])}",
                        mitigation_strategy="Implement fairness constraints, data rebalancing, threshold optimization",
                        responsible_party="ML Engineering Team",
                        timeline="0-14 days" if risk["severity"] == "CRITICAL" else "14-30 days",
                        success_metrics=[
                            "Disparate impact ratio > 0.8",
                            "Statistical parity < 0.1",
                            "Performance disparity < 20%"
                        ]
                    )

                elif "Security" in risk["nist_category"] or "Quality" in risk["nist_category"]:
                    quality_analysis = state.get("quality_analysis", {})

                    action = PrioritizedAction(
                        priority=priority,
                        risk_category=risk["nist_category"],
                        risk_description=f"Data quality issues: {quality_analysis.get('duplicate_percentage', 0):.1f}% duplicates",
                        mitigation_strategy="Implement deduplication pipeline, outlier handling, validation checks",
                        responsible_party="Data Engineering Team",
                        timeline="0-7 days" if risk["severity"] == "CRITICAL" else "7-14 days",
                        success_metrics=[
                            "Duplicate rate < 1%",
                            "Outlier percentage < 3%",
                            "Validation pipeline operational"
                        ]
                    )

                elif "Drift" in risk["nist_category"]:
                    drift_analysis = state.get("drift_analysis", {})

                    action = PrioritizedAction(
                        priority=priority,
                        risk_category=risk["nist_category"],
                        risk_description=f"Drift: {drift_analysis['drift_count']} features, {drift_analysis['bias_drift_count']} bias events",
                        mitigation_strategy="Emergency retraining, continuous monitoring, fairness restoration",
                        responsible_party="ML Operations Team",
                        timeline="0-7 days" if drift_analysis["bias_drift_count"] > 0 else "7-14 days",
                        success_metrics=[
                            "Drift metrics within thresholds",
                            "Fairness restored to baseline",
                            "Monitoring system operational"
                        ]
                    )

                else:
                    action = PrioritizedAction(
                        priority=priority,
                        risk_category=risk["nist_category"],
                        risk_description="; ".join(risk["findings"][:2]),
                        mitigation_strategy="Investigate and implement appropriate controls",
                        responsible_party="Governance Team",
                        timeline="7-14 days",
                        success_metrics=["Risk reduced to acceptable level"]
                    )

                actions.append(action)
                priority += 1

        return actions
