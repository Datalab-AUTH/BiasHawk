"""
Bias report handler: turn the technical metrics and warnings reports produced by
the bias assessment into an executive report.
"""

import logging

from core import llm

log = logging.getLogger("core.jobs.bias_report")

SYSTEM_PROMPT = (
    "You are an expert AI bias and fairness analyst. You have been given detailed "
    "technical reports from an automated bias analysis tool: a Metrics Report with "
    "quantitative measures (statistical parity, disparate impact, F1 scores across "
    "subgroups, representation percentages, proxy correlations, sensitive feature "
    "predictability) and a Warnings Report highlighting issues that exceeded "
    "predefined thresholds.\n\n"
    "Synthesise these into a comprehensive, human-readable Bias and Fairness "
    "Executive Report. Translate the technical data into actionable insights and "
    "strategic recommendations."
)

USER_PROMPT = """\
Analyse the following technical bias and fairness reports.

--- BEGIN METRICS REPORT ---
{metrics}
--- END METRICS REPORT ---

--- BEGIN WARNINGS REPORT ---
{warnings}
--- END WARNINGS REPORT ---

Generate a Bias and Fairness Executive Report with these sections:

1. **Executive Summary** , the most critical findings and the overall fairness
   posture (critical concerns, moderate issues, or generally fair).

2. **Key Findings & Observations** , the significant observations from both
   reports, each explained in practical terms. Group related findings, for
   instance by sensitive feature. Note where fairness looks acceptable too.

3. **Potential Risks & Impact** , the ethical, reputational, regulatory and
   business consequences of the identified biases, connected to specific
   findings.

4. **Actionable Recommendations** , specific mitigation steps, categorised
   (Data-Level, Model-Level, Monitoring & Governance) and prioritised
   (critical, high, medium). Explain which finding each one addresses.

5. **Conclusion** , why addressing these matters, and the next steps for
   ongoing fairness assurance.

Keep a professional, objective tone and briefly explain technical terms. The
audience is stakeholders who are not AI fairness specialists.
"""


def run(job):
    instance = job.instance
    if instance is None:
        raise ValueError("bias_report requires an instance.")

    if not instance.metrics_report or not instance.warnings_report:
        raise ValueError(
            "No bias assessment output to report on. Run the bias_assessment job first."
        )

    report = llm.chat(
        SYSTEM_PROMPT,
        USER_PROMPT.format(
            metrics=instance.metrics_report,
            warnings=instance.warnings_report,
        ),
    )

    instance.final_bias_report = report
    instance.save(update_fields=["final_bias_report", "updated_at"])

    return {"report_chars": len(report)}
