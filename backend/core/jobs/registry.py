"""
Job kind -> handler.

This dict is what replaced RabbitMQ routing. In the old stack, dispatching a
data quality run meant: publish to an exchange, a dedicated container consumes
it, computes, publishes a response, a fourteenth container consumes *that* and
writes the result to Postgres. Here a handler is a function that receives the
Job and writes to the model itself.

A handler:
  * takes one argument, the Job
  * may return a dict, which is stored on job.result
  * raises on failure; the runner records the traceback and retries
"""

import logging
from importlib import import_module

log = logging.getLogger("core.jobs")

# kind -> "module:function", imported lazily so a heavy handler's dependencies
# (torch, for instance) are only loaded if that kind is actually run.
_HANDLERS = {
    "rag_ingest": "core.jobs.rag_ingest:run",
    "usecase_extract": "core.jobs.usecase_extract:run",
    "instance_extract": "core.jobs.instance_extract:run",
    "data_governance": "core.jobs.data_governance:run",
    "data_quality": "core.jobs.data_quality:run",
    "sensitive_features": "core.jobs.sensitive_features:run",
    "bias_assessment": "core.jobs.bias_assessment:run",
    "bias_report": "core.jobs.bias_report:run",
    "drift": "core.jobs.drift:run",
    "risk_assessment": "core.jobs.risk_assessment:run",
}

_cache = {}


def register(kind, target):
    _HANDLERS[kind] = target
    _cache.pop(kind, None)


def known_kinds():
    return sorted(_HANDLERS)


def get_handler(kind):
    """Resolve a handler, or raise LookupError naming what is available."""
    if kind in _cache:
        return _cache[kind]

    target = _HANDLERS.get(kind)
    if target is None:
        raise LookupError(
            f"No handler registered for job kind {kind!r}. Known kinds: {', '.join(known_kinds()) or 'none'}"
        )

    module_path, _, attribute = target.partition(":")
    handler = getattr(import_module(module_path), attribute)
    _cache[kind] = handler
    return handler
