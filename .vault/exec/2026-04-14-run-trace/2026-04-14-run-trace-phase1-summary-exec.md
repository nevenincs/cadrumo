---
name: run-trace observability phase-1 summary
description: Execution summary for #99 run-trace + observability + dry-run replay
tags:
  - "#exec"
  - "#run-trace"
date: 2026-04-14
modified: '2026-04-14'
related:
  - "[[2026-04-14-run-trace-research]]"
  - "[[2026-04-14-run-trace-adr]]"
  - "[[2026-04-14-run-trace-plan]]"
---

# run-trace observability phase-1 summary

## status

Complete. Branch `feature/99-run-trace`, commit `ab397d4`, 46 files changed
(+3041 / -250). All four local gates green. Code review **APPROVED** by
`vaultspec-code-reviewer` with zero must-fix findings.

## what landed

- **New `src/aeat/core/observability/` subpackage** with strict pydantic v2
  `RunTrace`, `RunEvent`, `RunEventPayload` (tagged union with exactly-one
  invariant via `model_validator`), `ArgumentRecord`, and `StrEnum`s
  `RunEventKind`, `RunOutcome`, `ArgumentSource`.
- **Public API:** `run_context`, `record_event`, `replay_run`,
  `iter_runs`, `load_trace`, `load_events`, `save_trace`,
  `save_events_append`, `compute_corpus_sha256`, `compute_db_sha256`,
  `read_cert_fingerprint`, and all model / enum / error types.
- **contextvars propagation** via `_context.py` with nesting support
  (inner enter reuses outer run_id; pushes a new step_id).
- **Log-record factory** in `aeat.core.logging` (replaces the planned
  `logging.Filter` — filters only fire on originating loggers, not on
  parents reached via propagation; the executor caught this under test
  and switched to `setLogRecordFactory`, which stamps every record at
  creation time and is verified by `test_logging_filter.py`).
- **JSONL audit sink** (`JsonlRunSink`) attached per `run_context` entry,
  flushed after each record, fsync'd on close. Records carry
  `run_event: RunEvent` in `extra=`; bare log records stay out of the
  JSONL file.
- **Deterministic dry-run replay** (`replay_run`) with corpus-sha gate
  (`AeatCorpusDriftError`) and explicit refusal for `--no-dry-run`
  (`AeatObservabilityError`).
- **`aeat run` CLI** new top-level Typer subapp: `list`, `show`,
  `replay`. Registered under the root `app` alongside `aeat workflow`.
- **CLI wraps** at every outermost public entry point under
  `aeat.{submission,sync,inbox,status,workflow}` via
  `src/aeat/entrypoints/cli/_observability.py::cli_run_context`. The workflow `run`
  and `next` commands additionally emit `WORKFLOW_STARTED` /
  `WORKFLOW_COMPLETED` events linking the observability `run_id` to
  `WorkflowResult.run_id`.
- **Settings `aeat_runs_dir`** (additive) + matching
  `AEAT_RUNS_DIR=var/runs` line in `env/.env.example`.
  `tests/test_config.py` remains green.
- **Colocated unit tests** (all `@pytest.mark.unit`, no mocks/patches/
  fakes/stubs):
  `test_models.py`, `test_sink.py`, `test_context_propagation.py`,
  `test_logging_filter.py`, `test_replay.py`.

## deviations from plan

1. **Log record enrichment:** `setLogRecordFactory` replaces the planned
   `logging.Filter` on the root logger. Reason: filters attached to a
   logger only see records originating on that logger; records created
   on child loggers and propagated to root never trigger the filter.
   The factory stamps every record at creation, is universal, and sits
   in `aeat.core.logging` so `configure_logging()` does not need to import
   the observability package. Imports of the contextvars are lazy
   inside the factory closure to break the
   `logging → observability → config → auth → logging` cycle.
2. `_sink.py` dropped the `_RunContextFilter` / record-factory-install
   helpers after the relocation; only `JsonlRunSink` remains there.

Both deviations preserve the ADR contract (D4: every log record inside
a run context picks up the trace context).

## gates

- `uv run ruff check .` — green
- `uv run ty check src tests` — green
- `uv run pytest` — 900 passed, 1 skipped (full suite); 18 passed for
  the observability + config surface
- `uv run prek run --all-files` — green

## code review

`vaultspec-code-reviewer` ran against commit `ab397d4`. Verdict:
**APPROVED**. Zero must-fix findings; four LOW-severity observations,
none blocking. See review transcript in this session log.

## acceptance vs issue #99

All acceptance boxes satisfied:

- ✅ `RunTrace`, `RunEvent`, `ArgumentRecord` strict pydantic v2; all
  enums `StrEnum`.
- ✅ Every public CLI entry point under submission/sync/inbox/status/
  workflow emits ≥1 `RunEvent` with the active `run_id`.
- ✅ `aeat run replay <run_id> --dry-run` reproduces a recorded fixture
  run without contacting AEAT.
- ✅ JSONL run files round-trip via the pydantic models on read;
  invalid lines raise `RunTraceValidationError`.
- ✅ `.env.example` and `tests/test_config.py` aligned.

## follow-ups (out of scope, not blocking #99)

- Log rotation / retention policy for `var/runs/`.
- Integration with provenance trail from #82 (share the
  observability `run_id` as the provenance anchor).
- Live replay against a sandbox AEAT endpoint — not possible today
  because AEAT has no sandbox; live writes are legally binding.
