"""Run-trace observability layer.

Public API for cross-subpackage ``run_id`` propagation, JSONL audit
logging, and deterministic read-only replay.

Key surface area:

* :func:`run_context` — the contextvars-backed boundary that mints a
  ``run_id``, fingerprints corpus / db / cert state, and persists a
  :class:`RunTrace` on exit.
* :func:`record_event` — the single emit primitive every call site uses.
* :class:`RunEvent`, :class:`RunEventPayload`, :class:`RunTrace` —
  strict pydantic v2 record types written to JSONL.
* :func:`replay_run` — deterministic re-entry into a recorded run with
  an :class:`AeatCorpusDriftError` refusal gate.
* :func:`iter_runs` / :func:`iter_events` / :func:`load_trace` /
  :func:`load_events` — read-only accessors over persisted traces.
"""

from __future__ import annotations

from ._context import (
    RUN_CONTEXT_VAR,
    STEP_CONTEXT_VAR,
    RunContextInfo,
    current_run_context,
    run_context,
)
from ._errors import (
    AeatCorpusDriftError,
    AeatObservabilityError,
    RunContextMissingError,
    RunTracePersistenceError,
    RunTraceValidationError,
)
from ._fingerprint import (
    compute_corpus_sha256,
    compute_db_sha256,
    read_cert_fingerprint,
)
from ._models import (
    ArgumentRecord,
    ArgumentSource,
    AssertionPayload,
    CacheHitPayload,
    ErrorPayload,
    FormFillPayload,
    GenericPayload,
    NavigationPayload,
    RunEvent,
    RunEventKind,
    RunEventPayload,
    RunOutcome,
    RunTrace,
    StepBoundaryPayload,
    WorkflowLinkPayload,
)
from ._recorder import record_event
from ._replay import REPLAY_ACTIVE_ENV_VAR, replay_run
from ._store import (
    iter_events,
    iter_runs,
    load_events,
    load_trace,
    runs_dir,
    save_events_append,
    save_trace,
)

__all__ = [
    "REPLAY_ACTIVE_ENV_VAR",
    "RUN_CONTEXT_VAR",
    "STEP_CONTEXT_VAR",
    "AeatCorpusDriftError",
    "AeatObservabilityError",
    "ArgumentRecord",
    "ArgumentSource",
    "AssertionPayload",
    "CacheHitPayload",
    "ErrorPayload",
    "FormFillPayload",
    "GenericPayload",
    "NavigationPayload",
    "RunContextInfo",
    "RunContextMissingError",
    "RunEvent",
    "RunEventKind",
    "RunEventPayload",
    "RunOutcome",
    "RunTrace",
    "RunTracePersistenceError",
    "RunTraceValidationError",
    "StepBoundaryPayload",
    "WorkflowLinkPayload",
    "compute_corpus_sha256",
    "compute_db_sha256",
    "current_run_context",
    "iter_events",
    "iter_runs",
    "load_events",
    "load_trace",
    "read_cert_fingerprint",
    "record_event",
    "replay_run",
    "run_context",
    "runs_dir",
    "save_events_append",
    "save_trace",
]
