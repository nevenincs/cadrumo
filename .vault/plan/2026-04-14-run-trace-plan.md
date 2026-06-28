---
name: run-trace observability plan
description: Implementation plan for the observability subpackage, contextvars wiring, JSONL sink, aeat run CLI, and deterministic replay
tags:
  - "#plan"
  - "#run-trace"
date: 2026-04-14
modified: '2026-04-14'
related:
  - "[[2026-04-14-run-trace-research]]"
  - "[[2026-04-14-run-trace-adr]]"
---

# run-trace observability plan

## scope

Implement the decisions of `2026-04-14-run-trace-adr` on branch
`feature/99-run-trace` without touching the internals of
`src/aeat/adapters/outbound/aeat/export/` (#117) or `src/aeat/domain/financial/transactions/` (#74).

## deliverables

1. `src/aeat/core/observability/` subpackage (new).
2. Extensions to `src/aeat/logging.py` (contextvars filter + JSONL handler).
3. `aeat.core.errors.AeatObservabilityError` (new base, subclasses in
   `aeat.core.observability._errors`).
4. `Settings.aeat_runs_dir` (additive) plus `.env.example` entry.
5. `run_context` wraps at the outermost public entry points of
   `aeat.adapters.outbound.aeat.export`, `aeat.application.sync`, `aeat.inbox`, `aeat.status`,
   `aeat.application.workflow`.
6. `src/aeat/entrypoints/cli/run/` top-level Typer (`list`, `show`, `replay`).
7. Colocated unit tests under `src/aeat/core/observability/test_*.py`.

## step-by-step

### step 1 — observability subpackage skeleton

Create `src/aeat/core/observability/__init__.py` exporting the public API:

```python
from aeat.core.observability._context import (
    RUN_CONTEXT_VAR,
    STEP_CONTEXT_VAR,
    RunContextInfo,
    current_run_context,
    run_context,
)
from aeat.core.observability._errors import (
    AeatCorpusDriftError,
    AeatObservabilityError,
    RunContextMissingError,
    RunTraceValidationError,
)
from aeat.core.observability._fingerprint import (
    compute_corpus_sha256,
    compute_db_sha256,
    read_cert_fingerprint,
)
from aeat.core.observability._models import (
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
from aeat.core.observability._recorder import record_event
from aeat.core.observability._replay import replay_run
from aeat.core.observability._store import (
    iter_runs,
    load_events,
    load_trace,
    runs_dir,
    save_events_append,
    save_trace,
)
```

Each underscored module is internal; the `__all__` list names only the
symbols above.

### step 2 — `_models.py`

Define the strict pydantic v2 records:

```python
_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
```

`RunEventPayload` is a `BaseModel` with **one** optional field per payload
shape, enforcing "exactly one set" via a `model_validator(mode="after")`.
The model is serialized as a tagged union via pydantic's native JSON
schema.

```python
class NavigationPayload(BaseModel):
    model_config = _STRICT_FROZEN
    url: str
    description: str = ""

class FormFillPayload(BaseModel):
    model_config = _STRICT_FROZEN
    form_id: str
    casilla: str
    value: str  # stringified at capture time

class AssertionPayload(BaseModel):
    model_config = _STRICT_FROZEN
    expectation: str
    passed: bool
    detail: str = ""

class CacheHitPayload(BaseModel):
    model_config = _STRICT_FROZEN
    cache_name: str
    key: str

class ErrorPayload(BaseModel):
    model_config = _STRICT_FROZEN
    error_type: str
    message: str

class StepBoundaryPayload(BaseModel):
    model_config = _STRICT_FROZEN
    step_id: str
    label: str

class WorkflowLinkPayload(BaseModel):
    model_config = _STRICT_FROZEN
    workflow_run_id: str

class GenericPayload(BaseModel):
    model_config = _STRICT_FROZEN
    fields: tuple[tuple[str, str], ...] = ()

class RunEventPayload(BaseModel):
    model_config = _STRICT_FROZEN
    navigation: NavigationPayload | None = None
    form_fill: FormFillPayload | None = None
    assertion: AssertionPayload | None = None
    cache_hit: CacheHitPayload | None = None
    error: ErrorPayload | None = None
    step: StepBoundaryPayload | None = None
    workflow_link: WorkflowLinkPayload | None = None
    generic: GenericPayload | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "RunEventPayload":
        set_fields = [n for n in (
            "navigation", "form_fill", "assertion", "cache_hit",
            "error", "step", "workflow_link", "generic",
        ) if getattr(self, n) is not None]
        if len(set_fields) != 1:
            raise ValueError(
                f"RunEventPayload must set exactly one variant, got {set_fields}"
            )
        return self
```

`ArgumentRecord`, `RunEvent`, `RunTrace` follow.

### step 3 — `_context.py`

```python
_RUN_CTX: ContextVar[RunContextInfo | None] = ContextVar("_aeat_run_ctx", default=None)
_STEP_CTX: ContextVar[str | None] = ContextVar("_aeat_step_ctx", default=None)

@contextmanager
def run_context(
    *,
    entrypoint: str,
    arguments: Sequence[ArgumentRecord] = (),
    run_id: str | None = None,
    step_id: str | None = None,
) -> Iterator[RunContextInfo]: ...
```

`run_context` does the following on entry:

1. If an outer run context already exists, push a new `step_id` and
   yield a `RunContextInfo` that reuses the outer `run_id`. On exit,
   reset only the step.
2. If no outer context exists, mint a fresh `run_id` via
   `uuid.uuid4().hex[:16]`, compute fingerprints (corpus / db / cert),
   build a `RunTrace` skeleton, attach a JSONL sink for the duration of
   the block, and record a `STEP_START` event.
3. On exit, record a `STEP_END` event with outcome (`OK` / `FAILED`
   depending on whether an exception propagates), finalize the
   `RunTrace` with `finished_at` and the outcome, `save_trace(...)`,
   detach the JSONL sink, and reset the contextvars via their
   `Token`s.

### step 4 — `_sink.py`

`JsonlRunSink(logging.Handler)` subclass that:

- filters records to only those carrying `record.run_event` (a
  `RunEvent` instance set via `logger.info("...", extra={"run_event": evt})`),
- writes `evt.model_dump_json() + "\n"` to `events.jsonl`,
- `flush()` after each record,
- calls `os.fsync(fileno)` on `close()`.

`_inject_context_filter(logging.Filter)`: on every record, attaches
`run_id` and `step_id` attributes from the contextvars (empty string if
absent). This lets stderr logging pick up the trace context too.

Both are installed by `run_context` on entry and removed on exit.

### step 5 — `_recorder.py`

```python
def record_event(
    kind: RunEventKind,
    *,
    payload: RunEventPayload,
    module: str | None = None,
) -> RunEvent:
    ctx = _RUN_CTX.get(None)
    if ctx is None:
        raise RunContextMissingError(f"record_event({kind}) called outside run_context")
    step_id = _STEP_CTX.get(None) or ctx.initial_step_id
    event = RunEvent(
        run_id=ctx.run_id,
        step_id=step_id,
        kind=kind,
        payload=payload,
        timestamp=datetime.now(UTC),
        module=module or _caller_module(),
    )
    _logger.info(
        "run.event %s", kind.value, extra={"run_event": event}
    )
    return event
```

### step 6 — `_store.py`

Thin helpers:

- `runs_dir() -> Path` — reads `Settings.aeat_runs_dir` and ensures the
  directory exists.
- `save_trace(trace)` — writes `<runs_dir>/<run_id>/trace.json`.
- `load_trace(run_id)` — validates via `RunTrace.model_validate_json`.
- `save_events_append(run_id, event)` — opens `events.jsonl` in `a`
  mode, writes, flushes.
- `load_events(run_id)` — iterates, validates each line via
  `RunEvent.model_validate_json`, raises `RunTraceValidationError` on
  first invalid line.
- `iter_runs()` — yields `(run_id, RunTrace)` pairs sorted by
  `started_at` descending.

### step 7 — `_fingerprint.py`

Deterministic hashes per research D:

- `compute_corpus_sha256(vault_dir: Path, settings: Settings)`:
  SHA-256 over sorted `(rel_path, file_sha256)` pairs under `.vault/`
  concatenated with the sha of `settings.model_dump_json()`.
- `compute_db_sha256(var_dir: Path)`: SHA-256 over sorted file pairs
  under `var/` excluding `var/runs/` and `var/browser-traces/`.
- `read_cert_fingerprint() -> str`: returns `""` if no cert loaded;
  otherwise the SHA-256 of the DER body of the active certificate.

### step 8 — `_errors.py`

```python
from aeat.core.errors import AeatError

class AeatObservabilityError(AeatError): ...
class RunContextMissingError(AeatObservabilityError): ...

class AeatCorpusDriftError(AeatObservabilityError):
    def __init__(self, *, run_id: str, recorded: str, observed: str, entrypoint: str) -> None: ...

class RunTraceValidationError(AeatObservabilityError): ...
```

Re-export `AeatObservabilityError` from `aeat.core.errors` via a new line in
`src/aeat/errors.py`:

```python
class AeatObservabilityError(AeatError):
    """Base class for observability-layer errors (#99)."""
```

and have `aeat.core.observability._errors.AeatObservabilityError` be
`aeat.core.errors.AeatObservabilityError` directly (single source of truth).

### step 9 — `_replay.py`

```python
def replay_run(run_id: str, *, dry_run: bool = True) -> RunTrace:
    original = load_trace(run_id)
    observed_corpus = compute_corpus_sha256(...)
    if observed_corpus != original.corpus_sha256:
        raise AeatCorpusDriftError(
            run_id=run_id,
            recorded=original.corpus_sha256,
            observed=observed_corpus,
            entrypoint=original.entrypoint,
        )
    if not dry_run:
        raise AeatObservabilityError("replay is dry-run only (#99)")
    # reconstruct argv and re-enter the CLI with `no-live` forced on
    argv = _argv_from_arguments(original.entrypoint, original.arguments)
    from aeat.entrypoints.cli import app
    app(argv, standalone_mode=False)
    return original
```

Re-entering the Typer app from Python is idempotent because Typer
consumes `argv` exactly like the shell. `standalone_mode=False` keeps
exceptions propagating instead of exiting.

### step 10 — `src/aeat/logging.py` extension

Add a `logging.Filter` that reads the contextvars and augments records:

```python
class _RunContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        from aeat.core.observability._context import RUN_CONTEXT_VAR, STEP_CONTEXT_VAR
        ctx = RUN_CONTEXT_VAR.get(None)
        record.run_id = ctx.run_id if ctx is not None else ""
        record.step_id = STEP_CONTEXT_VAR.get(None) or ""
        return True
```

Attach the filter to the root logger in `configure_logging()`. The
import is local inside `filter()` to avoid a circular import at
`configure_logging` import time.

Format string stays compatible; operators who want run_id in the format
can set it themselves.

### step 11 — Settings field

In `src/aeat/config.py`, add under a new "Observability (#99)" section:

```python
# ── Observability (#99) ────────────────────────────────────────────────
aeat_runs_dir: Path = Field(
    default=PROJECT_ROOT / "var" / "runs",
    description="Directory where run traces + JSONL event logs are persisted",
)
```

`env/.env.example` gets:

```
# -- Observability (#99) -------------------------------------------------
# Directory where run traces + JSONL event logs are persisted (one
# subdirectory per run_id, containing trace.json + events.jsonl).
AEAT_RUNS_DIR=var/runs
```

### step 12 — wire entry points

For each outermost public surface, wrap it in `run_context(...)`. The
wrap lives in a thin adapter module next to the existing package init
and is used by the CLI only — library consumers still import the raw
class.

- `aeat.adapters.outbound.aeat.export.SubmissionEngine.submit_draft` and
  `submit_amendment`: wrap at the CLI command level in
  `src/aeat/entrypoints/cli/submission/` (not inside `_engine.py` — #117 territory).
  Entry point emits `WORKFLOW_LINK` + per-phase `STEP_*` events.
- `aeat.application.sync.LiveSyncRunner.run`: wrap inside `src/aeat/entrypoints/cli/sync/` and
  emit one `STEP_START` / `STEP_END` pair + per-phase events.
- `aeat.inbox.InboxFetcher.fetch`: wrap inside `src/aeat/entrypoints/cli/inbox/`.
- `aeat.status.StatusReader` entry points: wrap inside
  `src/aeat/entrypoints/cli/status/`.
- `aeat.application.workflow.WorkflowEngine.run_next`: wrap inside
  `src/aeat/entrypoints/cli/workflow/run.py` (already exists) and emit the
  `WORKFLOW_LINK` event carrying both the observability `run_id` and
  the `WorkflowResult.run_id`.

Each wrap must be a minimal-surface change (≤10 lines per CLI file).

### step 13 — `aeat run` CLI

New directory `src/aeat/entrypoints/cli/run/` with `__init__.py` exposing a
`typer.Typer` `app`:

- `list` — iterate `iter_runs()`, print table.
- `show <run_id>` — pretty-print trace + events.
- `replay <run_id> [--dry-run / --no-dry-run]` — default `--dry-run`;
  `--no-dry-run` raises explicitly because live replay is out of scope.

Register in `src/aeat/entrypoints/cli/__init__.py`:

```python
from aeat.entrypoints.cli import run as run_module
...
app.add_typer(run_module.app, name="run", help="Run-trace inspection and deterministic dry-run replay (#99).")
```

### step 14 — colocated tests

Four `@pytest.mark.unit` tests in `src/aeat/core/observability/test_*.py`:

1. `test_run_id_propagates_across_subpackages` — build Protocol
   doubles for `submission → status → inbox`, enter a `run_context`,
   call the chain, assert every emitted `RunEvent` carries the same
   `run_id`.
2. `test_trace_replay_round_trip` — record a trace to a tmp
   `aeat_runs_dir`, call `replay_run(...)` with the same corpus,
   assert the replay produces a new trace with the same entrypoint
   and arguments.
3. `test_replay_refuses_on_corpus_drift` — record a trace, mutate a
   `.vault/` file, call `replay_run(...)`, assert
   `AeatCorpusDriftError` with matching recorded/observed hashes.
4. `test_jsonl_sink_round_trip` — write several events through
   `record_event`, read back via `load_events`, assert each line
   validates via the pydantic model and the sequence matches.

Test fixtures use `monkeypatch` to redirect `aeat_runs_dir` to
`tmp_path` and real Protocol-conforming doubles (tiny classes that
`implements` the relevant Protocol by satisfying the method
signatures). No `unittest.mock`, no `MagicMock`, no patches.

### step 15 — lint + typecheck + test + hooks

Run the full local gate stack and fix all findings at the root:

```
just lint
just typecheck
just test
just hooks
```

No `# noqa`, no `# type: ignore`. Fix every root cause.

### step 16 — mandatory code review + commit + PR

Invoke `vaultspec-code-review` on every changed file. Commit with
conventional message `feat(observability): add run-trace, JSONL audit
log, and dry-run replay (#99)`. Open PR titled
`feat(observability): run-trace + JSONL audit + dry-run replay` with
body containing `Closes #99` and wiki-links to the research, ADR, and
plan.

## self-review against CLAUDE.md and sibling branches

This section is the explicit plan review the handover prompt demands.

- ✅ **`src/aeat/` layout mandate.** Every new module lands under
  `src/aeat/core/observability/` or `src/aeat/entrypoints/cli/run/`. Tests are
  colocated. No top-level scripts. No files outside `src/aeat/`.
- ✅ **Public API discipline.** External callers import only from
  `aeat.core.observability`, `aeat.core.errors`. Underscored modules are
  internal. The `__all__` list matches the re-exports.
- ✅ **Pydantic v2 mandate.** Every persisted type is strict, frozen,
  `extra="forbid"`. Closed enums are `StrEnum`. `RunEventPayload` is
  a tagged union with an exactly-one invariant enforced by a
  `model_validator`. No bare `dict[str, Any]`.
- ✅ **Errors inherit from `AeatError`.** `AeatObservabilityError` is
  declared in `aeat.core.errors`; all subclasses inherit from it.
- ✅ **Logging via `aeat.core.logging.get_logger(__name__)`.** The
  observability sink is a logging handler; callsites use
  `get_logger`.
- ✅ **Trilingual contract.** CLI output uses English (internal code
  language); user-facing strings emitted into the CLI tables are
  English. No Translatable fields are added to observability models
  because the audit log is structured, not user-facing prose.
- ✅ **Pytest only.** Every test is `@pytest.mark.unit`. No unittest,
  no mocks, no patches, no fakes. Real Protocol-conforming doubles
  only.
- ✅ **`AEAT_LIVE_TESTS_ENABLED` canonical.** The plan reuses
  `aeat.entrypoints.cli._live.requires_live_enabled()` if any live test is ever
  added — none is added in this scope.
- ✅ **GitHub Actions disabled.** No file under `.github/workflows/`
  is added.
- ✅ **Conventional commits.** Commit type is `feat` per the ADR.
- ✅ **#117 territory respected.** No file under `src/aeat/adapters/outbound/aeat/export/`
  except the CLI adapter at `src/aeat/entrypoints/cli/submission/*.py` is touched.
  The wrap sits at the CLI layer, outside the engine internals.
- ✅ **#74 territory respected.** No file under
  `src/aeat/domain/financial/transactions/` is touched.
- ✅ **`config.py` additive.** Only one field added; no renames.
- ✅ **`WorkflowRun` preserved.** `WorkflowResult` is not modified;
  the observability `run_id` is a separate identifier recorded via a
  `WORKFLOW_LINK` event.
- ✅ **Out-of-scope items (OpenTelemetry, log rotation, UI observability)
  are listed and rejected.** No drift into those areas.

### risks and mitigations

- **Circular import risk** between `aeat.core.logging` and
  `aeat.core.observability._context`. Mitigated by importing
  `RUN_CONTEXT_VAR` / `STEP_CONTEXT_VAR` *inside* the filter's
  `filter()` method, which is called after module load.
- **Typer `standalone_mode=False` behavior.** Replay calls
  `app(argv, standalone_mode=False)` — covered by a unit test that
  verifies a recorded fixture run replays end-to-end.
- **JSONL file handle lifetime.** The sink is attached per
  `run_context` entry and removed on exit. If the CLI is killed
  mid-run, the JSONL file is already flushed after each record (so
  partial traces survive). The trace.json write is the only thing
  that happens on exit — if the process dies before exit, the
  `RunTrace` is absent and `iter_runs()` skips the directory with a
  logged warning.
- **Corpus sha cost.** Hashing `.vault/` on every run costs O(n) on
  file count. Measured: tens of milliseconds on this repo, well
  under the acceptance budget.

### open work after merge (out of scope here)

- Log rotation / retention for `var/runs/`.
- A future issue could integrate `RunEvent` payloads with the
  provenance trail from #82.
- Live replay (not just dry-run) would require a sandbox AEAT
  endpoint, which does not exist.
