"""Run-trace observability layer (#99).

Public API for cross-subpackage ``run_id`` propagation, JSONL audit
logging, and deterministic dry-run replay. See [[2026-04-14-run-trace-adr]]
for the architecture and [[2026-04-14-run-trace-plan]] for the
implementation plan.
"""

from __future__ import annotations

from aeat.observability._context import (
    RUN_CONTEXT_VAR,
    STEP_CONTEXT_VAR,
    RunContextInfo,
    current_run_context,
    run_context,
)
from aeat.observability._errors import (
    AeatCorpusDriftError,
    AeatObservabilityError,
    RunContextMissingError,
    RunTraceValidationError,
)
from aeat.observability._fingerprint import (
    compute_corpus_sha256,
    compute_db_sha256,
    read_cert_fingerprint,
)
from aeat.observability._models import (
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
from aeat.observability._recorder import record_event
from aeat.observability._replay import replay_run
from aeat.observability._store import (
    iter_runs,
    load_events,
    load_trace,
    runs_dir,
    save_events_append,
    save_trace,
)

__all__ = [
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
    "RunTraceValidationError",
    "StepBoundaryPayload",
    "WorkflowLinkPayload",
    "compute_corpus_sha256",
    "compute_db_sha256",
    "current_run_context",
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
