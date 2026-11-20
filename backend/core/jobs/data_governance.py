"""
Data governance handler: profile the dataset, then have the model restructure
the profile into the reporting format.

Both artefacts are kept, as the old `data-governance` service did: the raw
profile from DataDescriber and the structured report the model writes from it.
The old stack stored them on the same two fields this does, and its UI offered
each as its own report.
"""

import logging

from core import llm
from core.analysis.governance import DataDescriber
from core.jobs._dataset import load_dataset

log = logging.getLogger("core.jobs.data_governance")

SYSTEM_PROMPT = "You are an AI assistant transforming data reports into a structured format."

OUTPUT_STRUCTURE = """\
## Structured Data Description Report

**1. Dataset Overview:**
   - Rows: [Number of rows]
   - Columns: [Number of columns]
   - Memory Usage: [Reported memory usage]
   - Duplicate Rows: [Number and percentage of duplicate rows]

**2. Data Types Composition:**
   - Summary: [Brief textual summary of the main data types present, e.g., "Primarily numeric with several categorical features."]
   - Breakdown: [List counts of major type categories like Numeric, Object/Categorical, Datetime, Boolean, if available in the input.]

**3. Missing Data Insights:**
   - Overall Status: [e.g., "No missing data detected", or "Missing values found in X columns."]
   - Key Columns Affected: [List columns with the highest percentage or count of missing values, mentioning the percentage.]

**4. Key Variable Characteristics:**
   - Constant/Low Variability: [Mention any columns identified with only one or very few unique values.]
   - High Cardinality: [Mention potential identifier columns or those with a very high number of unique values relative to row count.]
   - Notable Categorical Distributions: [Summarize key findings for categorical columns, e.g., dominant categories, skewed distributions mentioned in the input.]

**5. Date/Time Variables:**
   - Presence: [e.g., "X timestamp columns found", or "No timestamp columns detected."]
   - Time Range: [If available, report the earliest and latest timestamp and the overall duration.]
   - Unique Timestamps: [Report the number of unique timestamps if available.]

**6. Summary & Potential Focus Areas:**
   - Overall Impression: [A brief concluding summary of the dataset's characteristics based on the input report.]
   - Potential Actions/Checks: [Suggest areas needing attention based on the input, e.g., investigate missing values, confirm duplicate handling, examine low-variability features.]
"""

USER_PROMPT = """\
You are a data analyst assistant. Your task is to transform a raw data
description report (provided below in Markdown format) into a structured
summary report using a specific format.

**Input Data Description Report:**
```markdown
{profile}
```

**Instructions:** Analyze the input report and generate a new Markdown report
strictly following the structure defined below. Extract the relevant
information from the input report to fill in each section of the structure.
Summarize where appropriate, focusing on the key findings mentioned in the
input. If information for a specific point is not present in the input report,
state "Information not available in the provided report".

**Desired Output Structure:**
{structure}

Ensure the output is only the structured Markdown report, starting with
"## Structured Data Description Report".
"""

# The report's own heading. The old service asked up to three times and only
# accepted an answer carrying it, rather than saving whatever came back.
REPORT_MARKER = "Structured Data Description Report"
MAX_ATTEMPTS = 3


def _structured_report(profile):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        answer = llm.chat(
            SYSTEM_PROMPT,
            USER_PROMPT.format(profile=profile, structure=OUTPUT_STRUCTURE),
        )
        if answer and REPORT_MARKER in answer:
            return answer
        log.warning(
            "Attempt %d/%d did not return a structured report; asking again.",
            attempt,
            MAX_ATTEMPTS,
        )
    raise ValueError(
        f"The model did not return a structured data description report "
        f"after {MAX_ATTEMPTS} attempts."
    )


def run(job):
    instance = job.instance
    if instance is None:
        raise ValueError("data_governance requires an instance.")

    df, _ = load_dataset(instance)
    profile = DataDescriber(df).generate_summary_markdown()
    structured = _structured_report(profile)

    # Same split as the old pipeline: the profile is the description of the
    # data as measured, the structured report is the model's write-up of it.
    instance.data_profile_description = profile
    instance.data_quality_description = structured
    instance.save(
        update_fields=[
            "data_profile_description",
            "data_quality_description",
            "updated_at",
        ]
    )

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "profile_chars": len(profile),
        "report_chars": len(structured),
    }
