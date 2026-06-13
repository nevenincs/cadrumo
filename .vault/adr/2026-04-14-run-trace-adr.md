---
name: run-trace observability ADR
description: Architecture decisions for project-wide run_id propagation, JSONL audit log, and deterministic dry-run replay
tags:
  - "#adr"
  - "#run-trace"
date: 2026-04-14
modified: '2026-04-14'
related:
  - "[[2026-04-14-run-trace-research]]"
  - "[[2026-04-14-run-trace-plan]]"
  - "[[2026-04-12-workflow-engine-adr]]"
  - "[[2026-04-12-submission-engine-adr]]"
---

# run-trace observability ADR

## status

Accepted — 2026-04-14. Supersedes nothing.

## context

See `2026-04-14-run-trace-research`. The project needs a structured,
cross-subpackage run trace with deterministic dry-run replay so any past CLI
invocation can be reproduced for audit. This ADR records the decisions that
shape the implementation plan.

## decisions

### D1 — New `src/aeat/core/observability/` subpackage

A new subpackage owns all run-trace concerns. It lives at
`src/aeat/core/observability/`, follows public API discipline (callers import only
from `aeat.core.observability`, underscored modules are internal), and is not
consumed by any other subpackage at import time except as a top-level
context manager and `record_event` helper.

**Rationale:** keeps the blast radius small and matches the project's
subpackage-per-concern convention.

### D2 — `contextvars` propagation, outermost-only wrap

The run identifier and active step identifier live in
`contextvars.ContextVar` instances exposed through a `run_context()`
context manager. Entering the context manager sets the vars; exiting
resets them via the `contextvars.Token` returned by `var.set(...)`.
The context manager is entered **only at the outermost public entry point**
of each subpackage — not inside internal submodules. For `aeat.adapters.outbound.aeat.export`
we wrap `SubmissionEngine.submit_draft` / `submit_amendment` and nothing
else, to stay out of `#117`'s territory.

If `run_context()` is entered twice (nested), the inner entry reuses the
outer `run_id` and pushes a new `step_id`. This is idempotent and lets a
caller wrap a higher-level command without every callee needing to know
whether a run is already active.

**Rationale:** `contextvars` propagate through `asyncio.Task` boundaries
automatically, avoiding the `copy_context()` gymnastics other solutions
require. Nesting support means that when `aeat run replay` re-enters
workflow→submission→status it never double-counts.

### D3 — Strict pydantic v2 records, `StrEnum` for closed sets

Every persisted type is a strict, frozen, `extra="forbid"` pydantic v2
`BaseModel`. Closed enumerations are `enum.StrEnum`.

- `RunEventKind(StrEnum)`: `STEP_START`, `STEP_END`, `NAVIGATION`,
  `FORM_FILL`, `ASSERTION`, `CACHE_HIT`, `ERROR`, `WORKFLOW_STARTED`,
  `WORKFLOW_COMPLETED`.
- `RunOutcome(StrEnum)`: `OK`, `FAILED`, `ABORTED`.
- `ArgumentSource(StrEnum)`: `FLAG`, `ENV`, `CONFIG`, `DEFAULT`.
- `ArgumentRecord(BaseModel, frozen, strict)`: `name: str`,
  `value: str`, `source: ArgumentSource`. Values are serialized to strings at
  capture time so replay is deterministic.
- `RunEventPayload(BaseModel, frozen, strict)`: wraps arbitrary event
  fields via typed unions (see below).
- `RunEvent(BaseModel, frozen, strict)`: `run_id: str`, `step_id: str`,
  `kind: RunEventKind`, `payload: RunEventPayload`, `timestamp: datetime`,
  `module: str`.
- `RunTrace(BaseModel, frozen, strict)`: `run_id`, `started_at`,
  `finished_at: datetime | None`, `entrypoint: str`,
  `arguments: tuple[ArgumentRecord, ...]`, `corpus_sha256: str`,
  `db_sha256: str`, `cert_fingerprint: str`, `outcome: RunOutcome`.

Bare `dict[str, Any]` is banned. `RunEventPayload` uses a typed
discriminated union keyed on `kind` with a closed set of shapes
(`NavigationPayload`, `FormFillPayload`, `AssertionPayload`,
`CacheHitPayload`, `ErrorPayload`, `StepBoundaryPayload`,
`WorkflowLinkPayload`, `GenericPayload`). `GenericPayload` carries a
`tuple[tuple[str, str], ...]` (kv pairs of strings) so extensibility does
not fall back to an untyped dict.

### D4 — JSONL audit log, one file per run, append + fsync on close

Each run writes two files under `var/runs/<run_id>/`:

- `trace.json` — the `RunTrace` metadata, written once on context exit.
- `events.jsonl` — one line per `RunEvent`, append-only during the run.

Both round-trip through the pydantic models on read — any line that fails
strict validation raises `AeatObservabilityError` and aborts the CLI
command that attempted the read. The JSONL sink is implemented as a
`logging.Handler` subclass that filters records by the presence of a
`run_event` extra attribute; bare log records do not leak into
`events.jsonl`.

Log records emitted through `aeat.core.logging.get_logger(__name__)` still
reach stderr as today; the JSONL handler is an additive sink activated
only when a `run_context` is active. A dedicated `_inject_context_filter`
class adds `run_id`, `step_id`, `module` attributes to every
`logging.LogRecord` seen inside a run context, so existing log lines in
other subpackages automatically pick up the trace context without
edits.

### D5 — Deterministic dry-run replay, corpus-sha gate

`aeat run replay <run_id> --dry-run` loads the `RunTrace`, recomputes the
current `corpus_sha256`, and compares it against the recorded value.
- **Match:** replay reconstructs the captured arguments, re-enters the
  same CLI entry point (e.g. `aeat workflow run --modelo 130 ...`) with
  `--no-live` semantics forced on, and streams the new events into a
  fresh run directory under `var/runs/<replay_id>/`.
- **Drift:** replay refuses with `AeatCorpusDriftError` carrying both
  hashes and the entrypoint. The caller must resolve the drift by
  committing or reverting `.vault/` / Settings changes. Replay never
  contacts AEAT — the reuse-same-path invariant holds by construction
  because dry-run submission never sends a presentation POST.

**Rationale:** we want auditability, not time-travel. If the corpus
changed, the replay is no longer a reproduction — it is a new run with
different inputs, and refusing is the honest answer.

### D6 — `Settings.aeat_runs_dir` — purely additive

Add `aeat_runs_dir: Path = Path("var/runs")` (relative to `PROJECT_ROOT`).
`tests/test_config.py` passes because the new field has a default, and
`env/.env.example` gets a matching `AEAT_RUNS_DIR=var/runs` entry. No
existing field is renamed or removed — `#117` can add its own fields
without conflict.

### D7 — New CLI: `aeat run list/show/replay`

`aeat run` is a new top-level Typer sub-app registered alongside
`aeat workflow`. It does not subsume `aeat workflow run` (which kicks off
a workflow); instead it gives read/replay access to the observability
trace store:

- `aeat run list` — iterate `var/runs/*/trace.json`, print `run_id`,
  `started_at`, `entrypoint`, `outcome` as a table.
- `aeat run show <run_id>` — pretty-print the `RunTrace` and the event
  stream.
- `aeat run replay <run_id> --dry-run` — deterministic replay per D5.

### D8 — Errors inherit from `AeatError`

Four new errors live in `aeat.core.observability._errors`:
`AeatObservabilityError` (base), `RunContextMissingError`,
`AeatCorpusDriftError`, `RunTraceValidationError`. All subclass
`aeat.core.errors.AeatError` via a new `AeatObservabilityError` exported from
`aeat.core.errors` for import-time consumption.

## consequences

**Positive:**

- One audit record per CLI invocation, independent of which subpackage
  owns the work.
- Any past run is either reproducible end-to-end or explicitly refused
  with an actionable drift diff.
- Existing `logging.Logger` usage continues to work; the trace context
  enriches every log record without touching callsites.
- The observability layer is additive and non-blocking: if the CLI is
  invoked without a `run_context`, every subpackage still runs
  (with the caveat that `record_event` called outside a context raises
  — see Negative below).

**Negative:**

- Every public entry point must be entered through `run_context(...)`
  from the CLI, or `record_event` raises. The plan mitigates this by
  making `record_event` a no-op when `RUN_CONTEXT_VAR.get(None) is None`
  *outside* the CLI boundary, but strict inside. In practice: library
  consumers calling our subpackages from Python without the CLI get a
  no-op audit trail (which is the right default), while the CLI paths
  always produce a full trace.
- Wiring every entry point touches all five target subpackages.
- The JSONL directory grows unbounded. Log rotation/retention is an
  explicit follow-up, out of scope here.

## alternatives considered

- **OpenTelemetry exporter.** Rejected: pulls in a vendor-neutral
  tracing contract we do not need, complicates the local-only story,
  and couples the project to a runtime we cannot easily replace.
- **structlog.** Rejected: would require replacing every
  `logging.Logger` call site.
- **Passing `run_id` as an explicit argument through every function.**
  Rejected: N×M surface churn, breaks backward compatibility, and
  fights Python's `contextvars` idiom.
- **Persist events via `aeat.adapters.persistence.storage` (#10).** Rejected: `var/runs/`
  is the right container for ephemeral local audit data; storage is
  for long-lived, replicable state. If archival is ever needed, the
  JSONL files can be uploaded wholesale.

## acceptance

- `RunTrace`, `RunEvent`, `ArgumentRecord` all strict pydantic v2,
  `extra="forbid"`, `frozen=True`, `strict=True`.
- All enums `enum.StrEnum`.
- Every public entry point in `aeat.adapters.outbound.aeat.export`, `aeat.application.sync`,
  `aeat.inbox`, `aeat.status`, `aeat.application.workflow` emits ≥1 `RunEvent`
  with the active `run_id`.
- `aeat run replay <run_id> --dry-run` reproduces a recorded fixture
  run end-to-end without contacting AEAT; refuses on corpus sha drift.
- `events.jsonl` and `trace.json` round-trip through the pydantic models.
- `Settings.aeat_runs_dir` wired through `env/.env.example`;
  `tests/test_config.py` green.
- `just lint && just typecheck && just test && just hooks` all green on
  Windows.
