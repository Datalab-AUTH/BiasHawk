"""Enhanced Synthesis Agent - Production Version (BiasHawk v2.0)

Features:
- RAG-powered NIST guidance integration
- Intersectional bias analysis
- EU AI Act compliance assessment
- Generic for any AI system domain
- Factual data-driven analysis only
- No cost estimates or speculative content

Author: BiasHawk Team
Version: 2.0
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta

from core.risk.base import BaseAgent


class EnhancedSynthesisAgent(BaseAgent):
    """Production-grade synthesis agent for comprehensive NIST AI RMF reports."""

    TOOL_NAME = "BiasHawk"
    TOOL_VERSION = "2.0"

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive NIST risk assessment report."""

        print(f"\n[SYNTHESIS-{self.TOOL_NAME}] Generating enhanced report...")

        try:
            executive_summary = self._generate_executive_summary_enhanced(state)
            full_report = self._generate_full_report_enhanced(state, executive_summary)

            state["final_report"] = {
                "executive_summary": executive_summary,
                "full_report_markdown": full_report,
                "generated_at": datetime.now().isoformat(),
                "version": self.TOOL_VERSION,
                "tool": self.TOOL_NAME
            }

            word_count = len(full_report.split())
            print(f"  ✓ Report generated ({word_count:,} words)")

        except Exception as e:
            print(f"  ❌ ERROR in synthesis: {e}")
            import traceback
            traceback.print_exc()

            state["final_report"] = {
                "executive_summary": "Error generating enhanced report",
                "full_report_markdown": f"# Error\n\nReport generation failed: {e}",
                "generated_at": datetime.now().isoformat(),
                "version": self.TOOL_VERSION,
                "tool": self.TOOL_NAME
            }

        return state

    def _generate_executive_summary_enhanced(self, state: Dict[str, Any]) -> str:
        """Generate executive summary with RAG insights."""

        risk_summary = state.get("risk_summary", {})
        bias_analysis = state.get("bias_analysis", {})
        quality_analysis = state.get("quality_analysis", {})
        drift_analysis = state.get("drift_analysis", {})

        # RAG enhancement (optional)
        try:
            print("  [RAG] Retrieving NIST guidance...")
            nist_context = self.retrieve_nist_guidance(
                "executive summary risk assessment AI systems critical findings",
                n_results=2
            )
        except:
            nist_context = None

        bias_findings = bias_analysis.get("findings", [])
        critical_bias = [f for f in bias_findings if f.get("severity") == "CRITICAL"]
        high_bias = [f for f in bias_findings if f.get("severity") == "HIGH"]

        summary = "The risk assessment reveals "

        total_critical = risk_summary.get("critical_count", 0)
        total_high = risk_summary.get("high_count", 0)

        if total_critical > 0:
            summary += f"**CRITICAL** overall risk with {total_critical} critical issue(s) and {total_high} high-priority issue(s) requiring immediate attention. "
        elif total_high > 0:
            summary += f"**HIGH** overall risk with {total_high} high-priority issue(s). "
        else:
            summary += "**MEDIUM** risk levels. "

        # Critical bias findings
        if critical_bias:
            summary += f"\n\n**Critical Fairness Violations**: "
            for finding in critical_bias[:2]:
                dir_ratio = finding.get("disparate_impact_ratio", 0)
                attr = finding.get("attribute", "Unknown")
                gap_pct = (0.8 - dir_ratio) / 0.8 * 100
                fav_probs = finding.get("favorable_probabilities", {})
                if fav_probs:
                    probs_list = list(fav_probs.values())
                    outcome_gap = (max(probs_list) - min(probs_list)) * 100
                    summary += f"{attr} discrimination detected (DIR: {dir_ratio:.2f} - fails 80% rule by {gap_pct:.0f}%, {outcome_gap:.0f}% outcome gap); "
                else:
                    summary += f"{attr} (DIR: {dir_ratio:.2f} - fails by {gap_pct:.0f}%); "

        if high_bias:
            summary += f"\n\n**High Fairness Concerns**: "
            for finding in high_bias[:2]:
                dir_ratio = finding.get("disparate_impact_ratio", 0)
                attr = finding.get("attribute", "Unknown")
                summary += f"{attr} (DIR: {dir_ratio:.2f}, borderline); "

        # Quality issues
        dup_pct = quality_analysis.get("duplicate_percentage", 0)
        if dup_pct > 15:
            total_rows = quality_analysis.get("total_rows", 0)
            dup_rows = quality_analysis.get("duplicate_rows", 0)
            summary += f"\n\n**Data Quality Critical**: {dup_pct:.1f}% duplicate rows ({dup_rows:,} of {total_rows:,} rows) - data integrity issues may amplify bias. "

        # Drift analysis
        if drift_analysis.get("severity") in ["CRITICAL", "HIGH"]:
            drift_count = drift_analysis.get("drift_count", 0)
            bias_drift_count = drift_analysis.get("bias_drift_count", 0)
            summary += f"\n\n**Temporal Instability**: {drift_count} features show significant drift"
            if bias_drift_count > 0:
                summary += f" with {bias_drift_count} fairness degradation events"

            for event in drift_analysis.get("bias_drift_events", [])[:1]:
                baseline = event.get("baseline_value", 0)
                current = event.get("current_value", 0)
                change_pct = abs(current - baseline) / baseline * 100 if baseline != 0 else 0
                feature = event.get("feature", "")
                metric = event.get("metric", "")
                if "Disparate Impact" in metric:
                    summary += f". {feature} DIR declined from {baseline:.2f} → {current:.2f} (-{change_pct:.0f}%)"
            summary += ". "

        summary += f"\n\n**Immediate action required on {total_critical + total_high} priority risk(s).**"

        # RAG-enhanced compliance context (if available)
        if nist_context and self.llm:
            try:
                print("  [RAG] Generating compliance context...")
                legal_context = self.ask(
                    "You are an AI governance analyst. Answer in 1-2 sentences.",
                    "\n\n".join(
                        [
                            "Based on NIST AI RMF guidance, give 1-2 sentences on"
                            " the regulatory and compliance implications.",
                            f"NIST Context: {nist_context[:1500]}",
                            f"Risk Summary: {summary[:1000]}",
                            "Compliance Perspective (1-2 sentences):",
                        ]
                    ),
                )

                if legal_context and isinstance(legal_context, str) and len(legal_context.strip()) > 20:
                    summary += f"\n\n**Compliance Context**: {legal_context.strip()}"
            except Exception as e:
                print(f"  ⚠️ RAG enhancement skipped: {e}")

        return summary

    def _generate_full_report_enhanced(self, state: Dict[str, Any], exec_summary: str) -> str:
        """Generate complete report - generic for any AI system."""

        input_data = state.get("input_data", {})
        system_name = "Unknown System"
        system_domain = "Unknown"
        risk_category = "Unknown"

        if input_data.get("ai_system_documentation"):
            doc = input_data["ai_system_documentation"]
            general_info = doc.get("general_information", {})
            system_overview = doc.get("system_overview", {})

            system_name = general_info.get("ai_system_name", "Unknown System")
            system_domain = system_overview.get("domain_of_use", "Unknown")
            risk_category = system_overview.get("risk_category", "Unknown")

        risk_summary = state.get("risk_summary", {})

        report = f"""# AI System Risk Assessment Report

**AI System**: {system_name}
**Domain**: {system_domain}
**Risk Category**: {risk_category}
**Report Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Assessment Framework**: NIST AI Risk Management Framework (AI RMF 1.0)
**Report Version**: {self.TOOL_VERSION}
**Assessment Tool**: {self.TOOL_NAME}

---

## Executive Summary

{exec_summary}

**Overall Risk Distribution**:
- 🔴 Critical Risks: {risk_summary.get('critical_count', 0)}
- 🟠 High Risks: {risk_summary.get('high_count', 0)}
- 🟡 Medium Risks: {risk_summary.get('medium_count', 0)}
- 🟢 Low Risks: {risk_summary.get('low_count', 0)}

---

"""

        print("  [Generating] GOVERN section...")
        report += self._format_govern_section(state)
        report += "\n---\n\n"

        print("  [Generating] MAP section...")
        report += self._format_map_section(state)
        report += "\n---\n\n"

        print("  [Generating] MEASURE section...")
        report += self._format_measure_section(state)
        report += "\n---\n\n"

        print("  [Generating] MANAGE section...")
        report += self._format_manage_section(state)
        report += "\n---\n\n"

        print("  [Generating] Risk dashboard...")
        report += self._format_risk_dashboard(state)
        report += "\n---\n\n"

        print("  [Generating] Intersectional analysis...")
        report += self._format_intersectional_analysis(state)
        report += "\n---\n\n"

        print("  [Generating] EU AI Act compliance...")
        report += self._format_eu_ai_act_compliance(state)
        report += "\n---\n\n"

        print("  [Generating] Recommendations...")
        report += self._format_recommendations(state)

        return report

    def _format_govern_section(self, state: Dict) -> str:
        """GOVERN section - generic for any AI system."""

        governance = state.get("governance_analysis", {})
        input_data = state.get("input_data", {})

        content = """## 1. GOVERN: Governance and Oversight

### 1.1 Organizational Context
"""

        if input_data.get("ai_system_documentation"):
            doc = input_data["ai_system_documentation"]
            general_info = doc.get("general_information", {})
            system_overview = doc.get("system_overview", {})

            content += f"""
**AI System**: {general_info.get("ai_system_name", "Not specified")}
**Provider**: {general_info.get("provider_organization_name", "Not specified")}
**Responsible Party**: {general_info.get("responsible_person_team", "Not specified")}
**Contact**: {general_info.get("contact_information", "Not specified")}
**Version**: {general_info.get("version_release_date", "Not specified")}

**Purpose**: {system_overview.get("intended_purposes", "Not specified")}
**Domain**: {system_overview.get("domain_of_use", "Not specified")}
**User Groups**: {', '.join(system_overview.get("user_groups", ["Not specified"]))}
**Deployment**: {system_overview.get("deployment_environment", "Not specified")}
**Risk Category**: {system_overview.get("risk_category", "Not specified")}
"""

        content += f"""
### 1.2 Governance Maturity Assessment

**Score**: {governance.get('percentage', 0):.1f}% ({governance.get('score', 0)}/{governance.get('max_score', 100)})
**Risk Level**: {governance.get('severity', 'UNKNOWN')}

**Assessment**: Score of {governance.get('percentage', 0):.0f}% indicates {"strong" if governance.get('percentage', 0) > 80 else "moderate" if governance.get('percentage', 0) > 60 else "weak"} governance maturity.

**Findings**:
"""
        for finding in governance.get('findings', []):
            content += f"- {finding}\n"

        if input_data.get("ai_system_documentation"):
            doc = input_data["ai_system_documentation"]
            human_oversight = doc.get("human_oversight", {})
            cybersecurity = doc.get("cybersecurity", {})
            logging_doc = doc.get("logging_and_documentation", {})
            gdpr_assessment = doc.get("gdpr_conformity_assessment", {})

            content += f"""
### 1.3 Human Oversight

**Human-in-the-Loop**: {'✓ Yes' if human_oversight.get("human_in_the_loop", False) else '✗ No'}

**Oversight Procedures**:
"""
            for proc in human_oversight.get("oversight_procedures", []):
                content += f"- {proc}\n"

            if human_oversight.get("user_training"):
                content += "\n**User Training**:\n"
                for training in human_oversight.get("user_training", []):
                    content += f"- {training}\n"

            content += f"""
### 1.4 Cybersecurity

**Security Measures**:
"""
            for measure in cybersecurity.get("security_measures", []):
                content += f"- {measure}\n"

            if cybersecurity.get("robustness"):
                content += f"\n**Robustness Testing**: {cybersecurity.get('robustness')}\n"

            content += f"""
### 1.5 Logging & Auditability

**Logs Maintained**: {'✓ Yes' if logging_doc.get("logs_maintained", False) else '✗ No'}
**Retention Period**: {logging_doc.get("retention_period", "Not specified")}

**Auditability Features**:
"""
            for feature in logging_doc.get("auditability", []):
                content += f"- {feature}\n"

            if gdpr_assessment.get("assessment_performed"):
                content += f"""
### 1.6 Regulatory Conformity

**Assessment Performed**: {'✓ Yes' if gdpr_assessment.get("assessment_performed", False) else '✗ No'}
**Notified Body**: {gdpr_assessment.get("notified_body", "Not specified")}
**Outcome**: {gdpr_assessment.get("outcome", "Not specified")}
"""

        if input_data.get("data_compliance_form"):
            comp = input_data["data_compliance_form"]
            data_overview = comp.get("Data_Overview", {})
            collection_origin = comp.get("Data_Collection_and_Origin", {})
            management_gov = comp.get("Data_Management_and_Governance", {})

            content += f"""
### 1.7 Data Governance

**Data Sources**: {data_overview.get("Sources_of_Data", "Not specified")}
**High-Risk Data Handling**: {'⚠️ Yes' if data_overview.get("High_Risk_Data_Handling", False) else 'No'}

**Data Collection**:
- Consent Documented: {'✓ Yes' if collection_origin.get("Consent_Mechanism_Documented", False) else '✗ No'}
- Anonymization: {'✓ Applied' if collection_origin.get("Anonymization_or_Pseudonymization_Applied", False) else '✗ Not applied'}
- Sensitive Data: {'⚠️ Yes' if collection_origin.get("Sensitive_Data_Included", False) else 'No'}

**Data Management**:
- Regulatory Compliance: {'✓ Yes' if management_gov.get("Compliance_with_GDPR", False) else '✗ No'}
- Data Lineage: {'✓ Tracked' if management_gov.get("Data_Lineage_and_Provenance_Tracking", False) else '✗ Not tracked'}
- Retention Policy: {management_gov.get("Data_Retention_Policy", "Not specified")}
- Storage Location: {management_gov.get("Storage_Location_and_Jurisdiction", "Not specified")}
"""

        return content

    def _format_map_section(self, state: Dict) -> str:
        """MAP section - risk identification."""

        bias_analysis = state.get("bias_analysis", {})
        quality_analysis = state.get("quality_analysis", {})
        input_data = state.get("input_data", {})

        content = """## 2. MAP: Context and Risk Identification

### 2.1 AI System Context
"""

        if input_data.get("ai_system_documentation"):
            doc = input_data["ai_system_documentation"]
            model_algo = doc.get("model_and_algorithms", {})

            content += f"""
**Model Type**: {model_algo.get("model_type", "Not specified")}
**Training Algorithms**: {model_algo.get("training_algorithms", "Not specified")}
**Validation**: {model_algo.get("validation_methodology", "Not specified")}

**Explainability Techniques**:
"""
            for tech in model_algo.get("explainability_techniques", []):
                content += f"- {tech}\n"

        content += """
### 2.2 Risk Categorization

#### 2.2.6 Harmful Bias and Homogenization

"""

        bias_findings = bias_analysis.get("findings", [])
        if bias_findings:
            overall_severity = bias_analysis.get("severity", "UNKNOWN")
            content += f"**Risk Level**: {overall_severity}\n\n"

            # RAG enhancement for bias interpretation
            try:
                print("  [RAG] Enhancing bias risk analysis...")
                nist_bias_context = self.retrieve_nist_guidance(
                    "harmful bias disparate impact fairness discrimination",
                    n_results=2
                )

                if nist_bias_context and self.llm:
                    bias_interpretation = self.ask(
                        "You are an AI fairness analyst. Answer in 2-3 sentences.",
                        "\n\n".join(
                            [
                                "Based on NIST guidance, give 2-3 sentences on the"
                                " implications of these bias metrics.",
                                f"NIST Guidance: {nist_bias_context[:1500]}",
                                f"Bias Findings: {str(bias_findings[:2])}",
                                "Analysis (2-3 sentences):",
                            ]
                        ),
                    )

                    if bias_interpretation and isinstance(bias_interpretation, str):
                        content += f"**NIST-Based Assessment**: {bias_interpretation.strip()}\n\n"
            except Exception as e:
                print(f"  ⚠️ RAG bias analysis skipped: {e}")

            # Detailed findings
            for finding in bias_findings:
                attr = finding.get("attribute", "Unknown")
                dir_ratio = finding.get("disparate_impact_ratio", 1.0)
                stat_parity = finding.get("statistical_parity", 0.0)
                fav_probs = finding.get("favorable_probabilities", {})
                severity = finding.get("severity", "UNKNOWN")
                passes = finding.get("passes_80_rule", False)

                content += f"""
**{attr}** - Severity: {severity}
- Disparate Impact Ratio: {dir_ratio:.3f} {'✗ FAILS 80% rule' if not passes else '✓ Passes'}
- Statistical Parity: {stat_parity:.3f}

Favorable Outcome Probabilities:
"""
                for group, prob in fav_probs.items():
                    content += f"  - {group}: {prob:.1%}\n"

                if fav_probs:
                    probs = list(fav_probs.values())
                    gap = max(probs) - min(probs)
                    content += f"\nOutcome Gap: {gap:.1%}\n"

                    if not passes:
                        gap_pct = (0.8 - dir_ratio) / 0.8 * 100
                        content += f"\n**Assessment**: This {gap_pct:.0f}% failure below the 80% threshold indicates significant fairness concerns requiring immediate attention.\n"

                content += "\n"

        content += """
#### 2.2.9 Information Security (Data Quality)

"""

        quality_severity = quality_analysis.get("severity", "UNKNOWN")
        content += f"**Risk Level**: {quality_severity}\n\n"

        dup_pct = quality_analysis.get("duplicate_percentage", 0)
        dup_rows = quality_analysis.get("duplicate_rows", 0)
        total_rows = quality_analysis.get("total_rows", 0)

        content += f"- **Duplicates**: {dup_rows:,} rows ({dup_pct:.2f}% of {total_rows:,}) "
        if dup_pct > 20:
            content += "⚠️ CRITICAL\n"
        elif dup_pct > 15:
            content += "⚠️ HIGH\n"
        else:
            content += "\n"

        outlier_features = quality_analysis.get("outlier_features", [])
        if outlier_features:
            content += f"\n- **Outliers** in {len(outlier_features)} features:\n"
            for feat in outlier_features[:5]:
                content += f"  - {feat['feature']}: {feat['count']} outliers\n"

        return content

    def _format_measure_section(self, state: Dict) -> str:
        """MEASURE section - quantification."""

        quality_analysis = state.get("quality_analysis", {})
        bias_analysis = state.get("bias_analysis", {})
        drift_analysis = state.get("drift_analysis", {})

        content = f"""## 3. MEASURE: Assessment and Quantification

### 3.1 Data Quality Metrics

**Overall Assessment**: {quality_analysis.get('severity', 'UNKNOWN')}

- Total Rows: {quality_analysis.get('total_rows', 0):,}
- Duplicates: {quality_analysis.get('duplicate_percentage', 0):.2f}%
- Outlier Features: {len(quality_analysis.get('outlier_features', []))}
- Missing Data Features: {len(quality_analysis.get('missing_data_features', []))}

### 3.2 Bias Measurement

**Severity**: {bias_analysis.get('severity', 'UNKNOWN')}

| Attribute | DIR | Stat. Parity | 80% Rule | Severity |
|-----------|-----|--------------|----------|----------|
"""

        for finding in bias_analysis.get("findings", []):
            attr = finding.get("attribute", "Unknown")
            dir_ratio = finding.get("disparate_impact_ratio", 1.0)
            stat_parity = finding.get("statistical_parity", 0.0)
            passes = "PASS ✓" if finding.get("passes_80_rule", False) else "FAIL ✗"
            severity = finding.get("severity", "UNKNOWN")
            content += f"| {attr} | {dir_ratio:.3f} | {stat_parity:.3f} | {passes} | {severity} |\n"

        content += f"""
### 3.3 Data Drift Detection

**Severity**: {drift_analysis.get('severity', 'UNKNOWN')}
**Features with Drift**: {drift_analysis.get('drift_count', 0)}
**Fairness Degradation Events**: {drift_analysis.get('bias_drift_count', 0)}
"""

        drift_detected = drift_analysis.get("drift_detected", [])
        if drift_detected:
            content += "\n**Distribution Drift**:\n\n"
            content += "| Feature | Test | Metric | Severity |\n"
            content += "|---------|------|--------|----------|\n"

            for drift in drift_detected:
                feature = drift.get("feature", "Unknown")
                test = drift.get("test", "Unknown")
                severity = drift.get("severity", "UNKNOWN")

                if "p_value" in drift:
                    metric = f"p={drift['p_value']:.6f}"
                elif "jsd" in drift:
                    metric = f"JSD={drift['jsd']:.4f}"
                else:
                    metric = "N/A"

                content += f"| {feature} | {test} | {metric} | {severity} |\n"

        bias_drift_events = drift_analysis.get("bias_drift_events", [])
        if bias_drift_events:
            content += "\n**Fairness Degradation Over Time**:\n\n"
            content += "| Feature | Metric | Baseline | Current | Change |\n"
            content += "|---------|--------|----------|---------|--------|\n"

            for event in bias_drift_events:
                feature = event.get("feature", "Unknown")
                metric = event.get("metric", "Unknown")
                baseline = event.get("baseline_value", 0)
                current = event.get("current_value", 0)
                change = event.get("change", 0)
                content += f"| {feature} | {metric} | {baseline:.3f} | {current:.3f} | {change:+.3f} |\n"

        return content

    def _format_manage_section(self, state: Dict) -> str:
        """MANAGE section - mitigation actions."""

        actions = state.get("prioritized_actions", [])

        content = """## 4. MANAGE: Mitigation and Response

### 4.1 Prioritized Risk Management Actions

"""

        if not actions:
            content += "*No high-priority actions identified based on current risk levels.*\n"
        else:
            for action in actions:
                content += f"""
#### Priority {action.priority}: {action.risk_category}

**Risk Description**: {action.risk_description}

**Mitigation Strategy**: {action.mitigation_strategy}

**Responsible Party**: {action.responsible_party}

**Timeline**: {action.timeline}

**Success Metrics**:
"""
                for metric in action.success_metrics:
                    content += f"- {metric}\n"

                content += "\n"

        return content

    def _format_risk_dashboard(self, state: Dict) -> str:
        """Risk summary dashboard."""

        nist_mapping = state.get("nist_mapping", {})

        content = """## 5. Risk Summary Dashboard

| NIST Category | Risk Level | Status |
|---------------|------------|--------|
"""

        map_section = nist_mapping.get("MAP", {})
        for category, data in map_section.get("risk_categories", {}).items():
            risk_level = data.get("risk_level", "UNKNOWN")
            status = "🔴 Urgent" if risk_level in ["CRITICAL", "HIGH"] else "🟡 Monitor" if risk_level == "MEDIUM" else "🟢 Acceptable"
            content += f"| {category} | **{risk_level}** | {status} |\n"

        return content

    def _format_intersectional_analysis(self, state: Dict) -> str:
        """Intersectional fairness analysis."""

        input_data = state.get("input_data", {})
        bias_results = input_data.get("bias_assessment_results", {})

        content = """## 6. Intersectional Fairness Analysis

### 6.1 Compound Discrimination Assessment

"""

        if not bias_results:
            content += "*Intersectional analysis not available - no bias data provided.*\n"
            return content

        intersectional = bias_results.get("intersectional_fairness_metrics", {}).get("results", {})

        if not intersectional:
            content += """*Intersectional metrics not computed.*

**Recommendation**: Implement intersectional fairness analysis to detect compound discrimination patterns that single-attribute analysis may miss.

**Why This Matters**: Research shows discrimination often compounds across multiple protected characteristics. Testing for intersectional fairness is critical for comprehensive bias assessment.

**Implementation**: Compute fairness metrics for all combinations of protected attributes (e.g., age×gender, race×age, etc.) and test for interaction effects.
"""
            return content

        content += """Intersectional analysis examines how multiple protected characteristics combine to create compound discrimination effects.

**Intersectional Fairness Results**:

| Group Combination | DIR | Statistical Parity | Assessment | Severity |
|-------------------|-----|-------------------|------------|----------|
"""

        # Sort by DIR (worst first)
        sorted_intersectional = sorted(
            intersectional.items(),
            key=lambda x: x[1].get("Disparate Impact Ratio", 1.0)
        )

        worst_dir = None
        worst_group = None
        best_dir = None
        best_group = None

        for combo, metrics in sorted_intersectional:
            dir_ratio = metrics.get("Disparate Impact Ratio", 1.0)
            stat_parity = metrics.get("Statistical Parity", 0.0)

            if dir_ratio < 0.5:
                severity = "CRITICAL"
                assessment = "Severe compound discrimination"
            elif dir_ratio < 0.8:
                severity = "HIGH"
                assessment = "Fails 80% rule"
            elif dir_ratio < 0.9:
                severity = "MEDIUM"
                assessment = "Borderline fairness"
            else:
                severity = "LOW"
                assessment = "Acceptable"

            content += f"| {combo} | {dir_ratio:.3f} | {stat_parity:.3f} | {assessment} | {severity} |\n"

            if worst_dir is None or dir_ratio < worst_dir:
                worst_dir = dir_ratio
                worst_group = combo

            if best_dir is None or dir_ratio > best_dir:
                best_dir = dir_ratio
                best_group = combo

        if worst_group and worst_dir and worst_dir < 0.8:
            gap_from_best = (best_dir - worst_dir) if best_dir else 0
            content += f"""

### 6.2 Critical Finding: Compound Discrimination

**Most Disadvantaged Group**: {worst_group}
**Disparate Impact Ratio**: {worst_dir:.3f} (fails 80% rule by {((0.8 - worst_dir) / 0.8 * 100):.0f}%)

**Most Advantaged Group**: {best_group}
**Disparate Impact Ratio**: {best_dir:.3f}

**Intersectional Gap**: {gap_from_best:.3f} ({gap_from_best * 100:.0f} percentage points)

**Assessment**: This level of intersectional disparity indicates compound discrimination requiring targeted mitigation. Groups experiencing multiple forms of disadvantage face significantly worse outcomes.

**Recommended Actions**:
1. Implement intersectional fairness constraints in model training
2. Monitor outcomes for all demographic combinations
3. Test for interaction effects between protected attributes
4. Apply targeted interventions for compound-disadvantaged groups
5. Document intersectional fairness testing procedures
"""

        return content

    def _format_eu_ai_act_compliance(self, state: Dict) -> str:
        """EU AI Act compliance assessment."""

        input_data = state.get("input_data", {})
        governance_analysis = state.get("governance_analysis", {})
        quality_analysis = state.get("quality_analysis", {})
        bias_analysis = state.get("bias_analysis", {})

        # Determine if system is high-risk based on domain
        is_high_risk = False
        high_risk_reason = "Assessment pending"

        if input_data.get("ai_system_documentation"):
            doc = input_data["ai_system_documentation"]
            system_overview = doc.get("system_overview", {})
            risk_category = system_overview.get("risk_category", "").lower()
            domain = system_overview.get("domain_of_use", "").lower()

            # Check if it matches EU AI Act Annex III categories
            high_risk_keywords = [
                "employment", "workers", "recruitment", "hiring",
                "education", "training", "credit", "creditworthiness",
                "law enforcement", "migration", "asylum",
                "justice", "democratic processes"
            ]

            if any(keyword in risk_category or keyword in domain for keyword in high_risk_keywords):
                is_high_risk = True
                high_risk_reason = f"System domain ({domain}) or risk category ({risk_category}) matches EU AI Act Annex III high-risk AI systems"

        content = f"""## 7. EU AI Act Compliance Assessment

### 7.1 Risk Classification

**Classification**: {"HIGH-RISK AI SYSTEM" if is_high_risk else "ASSESSMENT REQUIRED"}
{"**Legal Basis**: EU AI Act Article 6(2) + Annex III" if is_high_risk else ""}

**Rationale**: {high_risk_reason}

"""

        if not is_high_risk:
            content += """**Note**: Based on available information, definitive risk classification requires review of system purpose and deployment context against EU AI Act Annex III categories.

**Next Steps**: 
1. Review system purpose against Annex III categories
2. Assess deployment context and intended users
3. Determine if system influences decisions in prohibited/high-risk areas
"""
            return content

        content += """### 7.2 Compliance Requirements Status

| Requirement | Article | Current Status | Gap Analysis |
|-------------|---------|----------------|--------------|
"""

        # Assess each requirement
        requirements = self._assess_eu_requirements(governance_analysis, quality_analysis, bias_analysis, input_data)

        compliant_count = 0
        partial_count = 0
        non_compliant_count = 0

        for req in requirements:
            content += f"| {req['requirement']} | {req['article']} | {req['status']} | {req['gap']} |\n"

            if "✅" in req['status']:
                compliant_count += 1
            elif "🟡" in req['status']:
                partial_count += 1
            elif "🔴" in req['status']:
                non_compliant_count += 1

        total_requirements = len(requirements)
        compliance_score = (compliant_count + partial_count * 0.5) / total_requirements * 100 if total_requirements > 0 else 0

        content += f"\n**Overall Compliance Score**: {compliance_score:.0f}% ({compliant_count}/{total_requirements} requirements fully met)\n\n"

        # Critical gaps
        critical_gaps = [req for req in requirements if "🔴" in req['status']]

        if critical_gaps:
            content += """### 7.3 Critical Compliance Gaps

The following requirements show non-compliance and require immediate attention:

"""
            for gap in critical_gaps:
                content += f"""**{gap['requirement']} ({gap['article']}) - CRITICAL**:
- Current Status: Non-compliant
- Gap: {gap['gap']}
- Required Action: {gap['action']}

"""

        content += f"""### 7.4 Regulatory Timeline

**Key Dates**:
- **August 1, 2024**: EU AI Act entered into force
- **February 2, 2026**: High-risk AI requirements enforceable (estimated)
- **August 2, 2026**: Full enforcement with penalties

**Enforcement**: National supervisory authorities in each EU member state

**Penalties for High-Risk Systems**:
- Non-compliance: Up to €35M or 7% of global annual turnover (whichever is higher)
- Incorrect information: Up to €7.5M or 1.5% of turnover

### 7.5 Recommended Compliance Actions

**Immediate (0-30 days)**:
- Address all critical gaps identified above
- Document current compliance measures
- Establish compliance monitoring procedures

**Short-term (30-90 days)**:
- Improve partial compliance areas
- Conduct internal compliance audit
- Update technical documentation

**Ongoing**:
- Monthly: Review compliance status
- Quarterly: External compliance review
- Annually: Submit post-market monitoring reports (when required)
"""

        return content

    def _assess_eu_requirements(self, governance, quality, bias, input_data) -> List[Dict]:
        """Assess EU AI Act compliance requirements."""

        requirements = []

        # Article 9 - Risk management
        has_risk_management = governance.get('score', 0) > 60
        requirements.append({
            'requirement': 'Risk management system',
            'article': 'Art. 9',
            'status': '✅ Compliant' if has_risk_management else '🟡 Partial',
            'gap': 'Risk assessment in place' if has_risk_management else 'Risk register needs formalization',
            'action': 'Maintain current process' if has_risk_management else 'Establish formal risk management system'
        })

        # Article 10 - Data governance
        has_data_gov = False
        data_gap = []
        if input_data.get("data_compliance_form"):
            comp = input_data["data_compliance_form"]
            has_consent = comp.get("Data_Collection_and_Origin", {}).get("Consent_Mechanism_Documented", False)
            has_anon = comp.get("Data_Collection_and_Origin", {}).get("Anonymization_or_Pseudonymization_Applied", False)
            sensitive_data = comp.get("Data_Collection_and_Origin", {}).get("Sensitive_Data_Included", False)

            if not has_consent:
                data_gap.append("No documented consent")
            if not has_anon and sensitive_data:
                data_gap.append("Sensitive data without anonymization")

            dup_pct = quality.get("duplicate_percentage", 0)
            if dup_pct > 5:
                data_gap.append(f"{dup_pct:.1f}% duplicates violate 'free of errors' requirement")

            has_data_gov = len(data_gap) == 0

        requirements.append({
            'requirement': 'Data governance',
            'article': 'Art. 10',
            'status': '✅ Compliant' if has_data_gov else '🔴 Non-compliant',
            'gap': 'Data governance practices in place' if has_data_gov else '; '.join(data_gap),
            'action': 'Maintain practices' if has_data_gov else 'Implement consent tracking and data quality controls'
        })

        # Article 11 - Technical documentation
        has_docs = input_data.get("ai_system_documentation") is not None
        requirements.append({
            'requirement': 'Technical documentation',
            'article': 'Art. 11',
            'status': '✅ Compliant' if has_docs else '🔴 Non-compliant',
            'gap': 'Documentation available' if has_docs else 'System documentation missing',
            'action': 'Keep updated' if has_docs else 'Create comprehensive system documentation'
        })

        # Article 12 - Record-keeping
        has_logs = False
        if input_data.get("ai_system_documentation"):
            doc = input_data["ai_system_documentation"]
            has_logs = doc.get("logging_and_documentation", {}).get("logs_maintained", False)

        requirements.append({
            'requirement': 'Record-keeping',
            'article': 'Art. 12',
            'status': '✅ Compliant' if has_logs else '🔴 Non-compliant',
            'gap': 'Audit logs maintained' if has_logs else 'No audit logging',
            'action': 'Continue logging' if has_logs else 'Implement comprehensive audit logging'
        })

        # Article 13 - Transparency
        has_transparency = has_docs  # Simplified check
        requirements.append({
            'requirement': 'Transparency',
            'article': 'Art. 13',
            'status': '🟡 Partial',
            'gap': 'System documentation exists; user-facing explanations may need enhancement',
            'action': 'Ensure end-user transparency and explainability'
        })

        # Article 14 - Human oversight
        has_oversight = False
        if input_data.get("ai_system_documentation"):
            doc = input_data["ai_system_documentation"]
            has_oversight = doc.get("human_oversight", {}).get("human_in_the_loop", False)

        requirements.append({
            'requirement': 'Human oversight',
            'article': 'Art. 14',
            'status': '✅ Compliant' if has_oversight else '🔴 Non-compliant',
            'gap': 'Human-in-the-loop measures in place' if has_oversight else 'No human oversight',
            'action': 'Maintain oversight' if has_oversight else 'Implement human review process'
        })

        # Article 15 - Accuracy, robustness, cybersecurity
        dup_pct = quality.get("duplicate_percentage", 0)
        has_accuracy = dup_pct < 5
        requirements.append({
            'requirement': 'Accuracy',
            'article': 'Art. 15(1)',
            'status': '✅ Compliant' if has_accuracy else '🔴 Non-compliant',
            'gap': 'Data quality acceptable' if has_accuracy else f'{dup_pct:.1f}% duplicates exceed threshold',
            'action': 'Monitor quality' if has_accuracy else 'Implement data quality controls'
        })

        has_security = False
        if input_data.get("ai_system_documentation"):
            doc = input_data["ai_system_documentation"]
            has_security = len(doc.get("cybersecurity", {}).get("security_measures", [])) > 0

        requirements.append({
            'requirement': 'Cybersecurity',
            'article': 'Art. 15(3)',
            'status': '✅ Compliant' if has_security else '🟡 Partial',
            'gap': 'Security measures documented' if has_security else 'Security measures need documentation',
            'action': 'Maintain security' if has_security else 'Document security measures'
        })

        return requirements

    def _format_recommendations(self, state: Dict) -> str:
        """Recommendations section."""
        import textwrap  # local import to support dedent

        actions = state.get("prioritized_actions", [])

        content = textwrap.dedent("""\
        ## 8. Recommendations and Next Steps

        ### 8.1 Immediate Actions (0-7 days)

        """)

        immediate = [a for a in actions if "0-7" in a.timeline or a.priority <= 2]
        if immediate:
            for action in immediate:
                # Plain text (no markdown bold) for better PDF rendering
                content += f"\n{action.risk_category}:\n"
                content += f"- Action: {action.mitigation_strategy}\n"
                content += f"- Owner: {action.responsible_party}\n"
                content += f"- Timeline: {action.timeline}\n"
                content += f"- Success: {', '.join(action.success_metrics[:2])}\n"
        else:
            content += "No urgent actions required based on current risk levels.\n"

        content += textwrap.dedent("""\

        ### 8.2 Short-Term Actions (7-30 days)

        """)

        short_term = [a for a in actions if "14-30" in a.timeline or "7-14" in a.timeline]
        if short_term:
            for action in short_term:
                # Plain text (no markdown bold)
                content += f"- {action.risk_category}: {action.mitigation_strategy}\n"
        else:
            content += "Review and monitor ongoing risk mitigation effectiveness.\n"

        content += textwrap.dedent("""\

        ### 8.3 Continuous Monitoring Framework

        Daily:
        - Data quality checks (duplicates, outliers, missing data)
        - Automated drift detection
        - Fairness metric monitoring

        Weekly:
        - Review fairness metrics for all protected attributes
        - Analyze demographic outcome distributions
        - Sample manual case reviews

        Monthly:
        - Comprehensive fairness report
        - Model performance assessment
        - Stakeholder review meeting

        Quarterly:
        - External fairness audit (if high-risk system)
        - Regulatory compliance review
        - Model refresh evaluation

        Key Performance Indicators:
        - Fairness: DIR ≥ 0.8 for all groups, Statistical Parity ≤ 0.1
        - Quality: Duplicate rate < 1%, Outlier rate < 3%
        - Drift: KS p-value > 0.05, JSD < 0.15
        - Governance: Audit log completeness 100%, Consent rate 100%

        ---

        ## Document Control

        """)

        # Generate dates dynamically
        assessment_date = datetime.now().strftime("%Y-%m-%d")
        next_review = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        # Plain text, no markdown formatting
        content += f"- Assessment Period: {assessment_date}\n"
        content += f"- Next Review Date: {next_review}\n"
        content += f"- Report Version: {self.TOOL_VERSION}\n"
        content += "- Classification: CONFIDENTIAL\n"
        content += f"- Prepared By: {self.TOOL_NAME} (Automated)\n"
        content += "\n---\n\n"

        # Footer - plain text
        content += (
            f"This automated risk assessment was generated by {self.TOOL_NAME} "
            "using the NIST AI Risk Management Framework. "
            "Review and validation by qualified professionals is recommended before making critical business decisions.\n"
        )

        return content


# Factory function for workflow initialization
