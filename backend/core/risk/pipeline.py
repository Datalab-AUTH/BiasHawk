"""
The risk assessment pipeline.

This replaces a LangGraph `StateGraph`. That graph declared seven nodes and six
edges wiring them in a straight line , governance, quality, bias, drift, NIST
mapping, prioritisation, synthesis , with no branches, no cycles and no
conditional routing. A `for` loop expresses the same thing, and it drops
langgraph, langgraph-checkpoint, langgraph-prebuilt, langgraph-sdk and
langchain-classic from the image.

Six of the seven agents are pure Python that reshape metrics into findings. Only
the synthesis agent calls an LLM, and only twice, to add NIST commentary to two
narrative sections.
"""

import logging
import time

from core.risk.document_analyzer import DocumentAnalyzerAgent
from core.risk.nist_mapper import NISTMapperAgent
from core.risk.risk_prioritizer import RiskPrioritizerAgent
from core.risk.synthesis import EnhancedSynthesisAgent

log = logging.getLogger("core.risk")


def build_agents():
    """The pipeline, in order. Each agent takes the state and returns it."""
    return [
        ("analyze_governance", DocumentAnalyzerAgent("governance")),
        ("analyze_quality", DocumentAnalyzerAgent("quality")),
        ("analyze_bias", DocumentAnalyzerAgent("bias")),
        ("analyze_drift", DocumentAnalyzerAgent("drift")),
        ("map_to_nist", NISTMapperAgent()),
        ("prioritize_risks", RiskPrioritizerAgent()),
        ("synthesize_report", EnhancedSynthesisAgent()),
    ]


def run(input_data):
    """
    Execute the pipeline over one instance's analysis results.

    Returns the final state: the per-area analyses, the NIST mapping, the
    prioritised actions and the report.
    """
    state = {
        "input_data": input_data,
        "quality_analysis": {},
        "bias_analysis": {},
        "drift_analysis": {},
        "governance_analysis": {},
        "nist_mapping": {},
        "prioritized_actions": [],
        "risk_summary": {},
        "final_report": {},
    }

    for name, agent in build_agents():
        started = time.monotonic()
        state = agent.process(state) or state
        log.info("risk pipeline: %-20s %.1fs", name, time.monotonic() - started)

    return state
