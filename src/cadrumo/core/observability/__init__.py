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

from ._capture import (
    capture_envelopes,
    capture_is_armed,
    record_emitted_envelope,
)
from ._context import (
    RUN_CONTEXT_VAR,
    STEP_CONTEXT_VAR,
    RunContextInfo,
    current_run_context,
    run_context,
)
from ._errors import (
    AeatCorpusDriftError,
    CadrumoObservabilityError,
    GoldenCaptureError,
    GoldenReplayMismatchError,
    RunContextMissingError,
    RunTracePersistenceError,
    RunTraceValidationError,
)
from ._fingerprint import (
    compute_corpus_sha256,
    compute_db_sha256,
    read_cert_fingerprint,
)
from ._golden import (
    GOLDEN_MASK_FIELDS,
    GOLDEN_MASK_PATHS,
    MASK_SENTINEL,
    assert_golden_match,
    canonicalise,
    differing_field_names,
    differing_paths,
    flatten_paths,
    mask_document,
    validate_captured_envelope,
)
from ._models import (
    RUN_ID_PATTERN,
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
    RunId,
    RunOutcome,
    RunTrace,
    StepBoundaryPayload,
    WorkflowLinkPayload,
)
from ._recorder import record_event
from ._replay import REPLAY_ACTIVE_ENV_VAR, replay_run
from ._sink import JsonlRunSink
from ._store import (
    ENVELOPE_FILENAME,
    EVENTS_FILENAME,
    TRACE_FILENAME,
    iter_events,
    iter_runs,
    load_envelope_document,
    load_events,
    load_trace,
    runs_dir,
    save_envelope,
    save_events_append,
    save_trace,
)

__all__ = [
    "ENVELOPE_FILENAME",
    "EVENTS_FILENAME",
    "GOLDEN_MASK_FIELDS",
    "GOLDEN_MASK_PATHS",
    "MASK_SENTINEL",
    "REPLAY_ACTIVE_ENV_VAR",
    "RUN_CONTEXT_VAR",
    "RUN_ID_PATTERN",
    "STEP_CONTEXT_VAR",
    "TRACE_FILENAME",
    "AeatCorpusDriftError",
    "ArgumentRecord",
    "ArgumentSource",
    "AssertionPayload",
    "CacheHitPayload",
    "CadrumoObservabilityError",
    "ErrorPayload",
    "FormFillPayload",
    "GenericPayload",
    "GoldenCaptureError",
    "GoldenReplayMismatchError",
    "JsonlRunSink",
    "NavigationPayload",
    "RunContextInfo",
    "RunContextMissingError",
    "RunEvent",
    "RunEventKind",
    "RunEventPayload",
    "RunId",
    "RunOutcome",
    "RunTrace",
    "RunTracePersistenceError",
    "RunTraceValidationError",
    "StepBoundaryPayload",
    "WorkflowLinkPayload",
    "assert_golden_match",
    "canonicalise",
    "capture_envelopes",
    "capture_is_armed",
    "compute_corpus_sha256",
    "compute_db_sha256",
    "current_run_context",
    "differing_field_names",
    "differing_paths",
    "flatten_paths",
    "iter_events",
    "iter_runs",
    "load_envelope_document",
    "load_events",
    "load_trace",
    "mask_document",
    "read_cert_fingerprint",
    "record_emitted_envelope",
    "record_event",
    "replay_run",
    "run_context",
    "runs_dir",
    "save_envelope",
    "save_events_append",
    "save_trace",
    "validate_captured_envelope",
]
