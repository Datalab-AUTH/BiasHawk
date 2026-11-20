"""
Base class for the risk assessment agents.

The old base built a `ChatOpenAI` per agent behind a `USE_OPENAI` switch and
held a ChromaDB-backed knowledge base. Both are gone: LLM calls go through
`core.llm` (Open WebUI only) and NIST guidance comes from pgvector.
"""

from abc import ABC, abstractmethod

from core import llm
from core.risk import knowledge_base


class BaseAgent(ABC):
    """An agent takes the shared state dict, adds to it, and returns it."""

    def retrieve_nist_guidance(self, query, n_results=3):
        return knowledge_base.guidance_text(query, n_results)

    def ask(self, system, user):
        """
        One LLM call, returning "" on failure.

        The synthesis agent uses this only to enrich narrative sections with
        NIST commentary; a failure there should not lose an otherwise complete
        report, so it degrades to omitting that paragraph.
        """
        try:
            return llm.chat(system, user, temperature=0.1)
        except Exception:
            return ""

    @property
    def llm(self):
        """Truthy so the ported `if ... and self.llm:` guards still read naturally."""
        return True

    @abstractmethod
    def process(self, state):
        """Do this agent's work and return the updated state."""
