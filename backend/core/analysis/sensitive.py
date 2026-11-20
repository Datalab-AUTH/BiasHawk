"""
Sensitive feature detection.

Ported from the old `sensitive_features_agent`. The detection logic , keyword
matching against the knowledge base, then an LLM pass, then combining the two ,
is unchanged. What went away is LangChain: the old client built a
ChatPromptTemplate piped into a PydanticOutputParser purely to get one JSON
object back. Here the prompt asks for JSON and pydantic validates it.
"""

import json
import logging
import re

from pydantic import BaseModel, Field, ValidationError

from core import llm
from core.analysis.sensitive_kb import KNOWLEDGE_BASE

log = logging.getLogger("core.analysis.sensitive")

SYSTEM_PROMPT = (
    "You are an AI assistant that generates JSON data. You MUST output a single "
    "valid JSON object and nothing else , no explanation, no preamble, no code "
    "fence. The object must be an instance conforming to the requested fields, "
    "not a reproduction of the schema."
)

USER_PROMPT = """\
Analyze the feature below using its name, its description, the knowledge base,
and your understanding of AI ethics, NIST SP 1270 and the EU AI Act.

Knowledge base summary:
{kb_summary}

Feature to analyze:
  Name: "{feature_name}"
  Description: "{feature_description}"

Produce a JSON object with exactly these fields:
- "feature_name": string , exactly "{feature_name}"
- "is_sensitive": boolean
- "assessment_score_contribution": integer 0-100, sensitivity score; 0 if not sensitive
- "identified_categories": array of objects, each with "category_name" (from the
  knowledge base, e.g. "RACE_ETHNICITY") and "reasoning" (string). Empty when
  "is_sensitive" is false.
- "overall_llm_reasoning": string

Example when sensitive:
{{"feature_name":"user_age_field","is_sensitive":true,"assessment_score_contribution":70,
"identified_categories":[{{"category_name":"AGE","reasoning":"Name and description directly indicate age."}}],
"overall_llm_reasoning":"Sensitive: pertains to AGE."}}

Example when not sensitive:
{{"feature_name":"product_sku","is_sensitive":false,"assessment_score_contribution":0,
"identified_categories":[],"overall_llm_reasoning":"An inventory identifier; not sensitive."}}

Output only the JSON object for "{feature_name}".
"""


class CategoryDetail(BaseModel):
    category_name: str = ""
    reasoning: str = ""


class FeatureAnalysis(BaseModel):
    feature_name: str
    is_sensitive: bool = False
    assessment_score_contribution: int = Field(default=0, ge=0, le=100)
    identified_categories: list[CategoryDetail] = Field(default_factory=list)
    overall_llm_reasoning: str = ""


def _build_keyword_map():
    """Longest keywords first, so "date_of_birth" wins over "birth"."""
    keyword_map = [
        (keyword.lower(), keyword, category)
        for category, info in KNOWLEDGE_BASE.items()
        for keyword in info["keywords"]
    ]
    keyword_map.sort(key=lambda item: len(item[0]), reverse=True)
    return keyword_map


KEYWORD_MAP = _build_keyword_map()


def _kb_summary():
    lines = ["Sensitive Categories Overview:"]
    for category, info in KNOWLEDGE_BASE.items():
        lines.append(
            f"- Category: {category}\n"
            f"  Description: {info['description']}\n"
            f"  Keywords (examples): {', '.join(info['keywords'][:5])}\n"
            f"  Rationale: {info['rationale']}\n"
            f"  Base Score: {info['base_sensitivity_score']}\n"
        )
    return "\n".join(lines)


KB_SUMMARY = _kb_summary()


def _normalise(text):
    return (text or "").lower().replace("_", " ").replace("-", " ")


def detect_by_keyword(feature_name, feature_description=""):
    """Knowledge-base keyword hits in the feature's name or description."""
    hits = []
    sources = [("name", _normalise(feature_name))]
    if feature_description:
        sources.append(("description", _normalise(feature_description)))

    for origin, text in sources:
        for keyword_lower, keyword, category in KEYWORD_MAP:
            if not re.search(r"\b" + re.escape(keyword_lower) + r"\b", text):
                continue
            if any(hit["category_name"] == category for hit in hits):
                continue
            hits.append(
                {
                    "category_name": category,
                    "matched_keyword": keyword,
                    "reasoning": (
                        f"Direct keyword match for '{keyword}' in the feature {origin}. "
                        f"{KNOWLEDGE_BASE[category]['rationale']}"
                    ),
                    "sources": KNOWLEDGE_BASE[category]["sources"],
                }
            )
    return hits


def _extract_json(text):
    """Models sometimes wrap JSON in a code fence despite instructions."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in the model's reply.")
    return json.loads(text[start : end + 1])


def analyse_feature_with_llm(feature_name, feature_description):
    """One LLM verdict on one feature. Never raises , falls back to not-sensitive."""
    try:
        reply = llm.chat(
            SYSTEM_PROMPT,
            USER_PROMPT.format(
                kb_summary=KB_SUMMARY,
                feature_name=feature_name,
                feature_description=feature_description or "No description provided.",
            ),
        )
        parsed = FeatureAnalysis.model_validate(_extract_json(reply))
        return parsed.model_dump()
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        log.warning("Could not parse the model's verdict on %r: %s", feature_name, exc)
        reasoning = f"The model's reply for '{feature_name}' could not be parsed: {exc}"
    except Exception as exc:
        log.warning("LLM assessment of %r failed: %s", feature_name, exc)
        reasoning = f"LLM assessment of '{feature_name}' failed: {exc}"

    return FeatureAnalysis(
        feature_name=feature_name, overall_llm_reasoning=reasoning
    ).model_dump()


def analyse_features(feature_descriptions):
    """
    Assess every feature, keyword pass then LLM pass.

    Args:
        feature_descriptions: {column name: description}

    Returns:
        A list of sensitive features, highest assessment score first.
    """
    results = []

    for feature_name, feature_description in feature_descriptions.items():
        keyword_hits = detect_by_keyword(feature_name, feature_description)
        by_keyword = bool(keyword_hits)
        keyword_score = max(
            (KNOWLEDGE_BASE[hit["category_name"]]["base_sensitivity_score"] for hit in keyword_hits),
            default=0,
        )
        keyword_details = [
            {
                "category_name": hit["category_name"],
                "source_detection": "keyword",
                "details": hit["reasoning"],
                "matched_keyword": hit["matched_keyword"],
                "references": hit["sources"],
            }
            for hit in keyword_hits
        ]

        verdict = analyse_feature_with_llm(feature_name, feature_description)
        by_llm = verdict["is_sensitive"]
        llm_details = [
            {
                "category_name": category["category_name"],
                "source_detection": "llm",
                "details": category["reasoning"] or "No reasoning given.",
                "references": KNOWLEDGE_BASE.get(category["category_name"], {}).get(
                    "sources", ["LLM discretion"]
                ),
            }
            for category in verdict["identified_categories"]
            if (category["category_name"] or "").strip().lower() not in ("", "none")
        ] if by_llm else []

        if not (by_keyword or by_llm):
            log.debug("Feature %r assessed as not sensitive.", feature_name)
            continue

        score = keyword_score
        if by_llm:
            score = max(score, verdict["assessment_score_contribution"])
        # Flagged sensitive but scored zero: keep it visible at the bottom.
        score = score or 10

        # Keep both sources when they disagree , which of them fired is itself
        # information, and the old code lost it through over-eager deduplication.
        combined, seen = [], set()
        for detail in keyword_details + llm_details:
            key = (detail["category_name"], detail["source_detection"], detail["details"])
            if key not in seen:
                seen.add(key)
                combined.append(detail)

        # Which of the two sources fired is shown as its own badge next to the
        # feature, so appending it to the reasoning only repeated it in prose.
        summary = verdict["overall_llm_reasoning"]

        results.append(
            {
                "feature_name": feature_name,
                "feature_description": feature_description,
                "overall_assessment_score": score,
                "is_sensitive_by_keyword": by_keyword,
                "is_sensitive_by_llm": by_llm,
                "identified_categories_details": combined,
                "llm_assessment_summary": summary,
            }
        )

    results.sort(key=lambda item: item["overall_assessment_score"], reverse=True)
    return results
